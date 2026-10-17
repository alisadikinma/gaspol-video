import unittest
from unittest import mock

from tools import face_box


class FrameIndices(unittest.TestCase):
    def test_every_n_picks_multiples(self):
        self.assertEqual(face_box.frame_indices(10, 3), [0, 3, 6, 9])

    def test_every_one_is_all(self):
        self.assertEqual(face_box.frame_indices(3, 1), [0, 1, 2])

    def test_zero_frames(self):
        self.assertEqual(face_box.frame_indices(0, 5), [])

    def test_bad_step_raises(self):
        for n in (0, -2):
            with self.assertRaises(ValueError):
                face_box.frame_indices(10, n)


class BoxConversion(unittest.TestCase):
    def test_absolute_origin_size(self):
        self.assertEqual(face_box.to_pixel_box(100, 200, 50, 80, 1080, 1920), [100, 200, 150, 280])

    def test_relative_origin_size(self):
        self.assertEqual(face_box.to_pixel_box(0.1, 0.5, 0.2, 0.1, 1000, 2000, relative=True),
                         [100, 1000, 300, 1200])

    def test_clamped_to_frame_end_exclusive(self):
        self.assertEqual(face_box.to_pixel_box(-5, -5, 2000, 3000, 1080, 1920), [0, 0, 1080, 1920])

    def test_ints(self):
        box = face_box.to_pixel_box(10.4, 10.6, 20.2, 20.2, 100, 100)
        self.assertTrue(all(isinstance(v, int) for v in box))


class Record(unittest.TestCase):
    def test_none_box(self):
        self.assertEqual(face_box.record(4, 25.0, None), {"frame": 4, "t": 0.16, "box": None})

    def test_with_box(self):
        self.assertEqual(face_box.record(0, 30.0, [1, 2, 3, 4]),
                         {"frame": 0, "t": 0.0, "box": [1, 2, 3, 4]})


class Boxes(unittest.TestCase):
    def test_uses_injected_detector_on_selected_frames(self):
        w, h = 4, 4
        frames = [bytes([i]) * (w * h * 3) for i in range(7)]
        seen = []

        def detect(rgb, index, ww, hh):
            seen.append(index)
            return [1, 1, 3, 3] if index == 3 else None

        with mock.patch.object(face_box, "probe", return_value=(w, h, 10.0, 7)), \
                mock.patch.object(face_box, "read_frames", return_value=iter(frames)):
            out = face_box.boxes("x.mp4", 3, detect)
        self.assertEqual(seen, [0, 3, 6])
        self.assertEqual(out, [
            {"frame": 0, "t": 0.0, "box": None},
            {"frame": 3, "t": 0.3, "box": [1, 1, 3, 3]},
            {"frame": 6, "t": 0.6, "box": None},
        ])

    def test_unreadable_video(self):
        with mock.patch.object(face_box, "probe", return_value=(0, 0, 0.0, 0)):
            with self.assertRaises(face_box.VideoUnreadable):
                face_box.boxes("nope.mp4", 1, lambda *a: None)


class Cli(unittest.TestCase):
    def test_missing_model_exit_2_names_setup(self):
        with mock.patch.object(face_box, "model_path", return_value=face_box.Path("/nonexistent/m.tflite")), \
                mock.patch("sys.stderr") as err:
            rc = face_box.main(["x.mp4"])
        self.assertEqual(rc, 2)
        self.assertIn("tools/setup.sh", "".join(c.args[0] for c in err.write.call_args_list))

    def test_unreadable_video_exit_2(self):
        with mock.patch.object(face_box, "probe", return_value=(0, 0, 0.0, 0)), \
                mock.patch.object(face_box, "make_detector", return_value=lambda *a: None):
            self.assertEqual(face_box.main(["nope.mp4"]), 2)


if __name__ == "__main__":
    unittest.main()
