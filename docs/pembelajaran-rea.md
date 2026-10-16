# Pembelajaran dari video REA (Reverse Engineer Anything)

Dari satu reel referensi sampai video final 93 detik, suara Ali sendiri, tujuh kelompok scene.
Isi di bawah dipakai oleh `skills/video-repackage`. Tiap poin: apa yang terjadi, lalu aturannya.

## 1. Alur kerja

- Kerjakan per kelompok (maks 5 scene): naskah suara dulu, lalu klip VEO, ganti suara, Remotion, potong, persetujuan. Lalu baru final (sambung, SFX, musik, subtitle, loudness).
  Alasan: salah yang ketahuan di kelompok hanya merusak 5 scene, bukan seluruh video.
- Panjang klip ditentukan panjang suara, bukan sebaliknya.
- Jangan generate ulang klip atau gambar tanpa tanya. Satu kali saya memakai kredit VEO tanpa izin, dan itu salah.
- Setelah revisi, jalankan ulang seluruh rantai (klip, ganti suara, overlay, potongan, final). Satu yang basi merusak hasil.

## 2. Suara

- Satu suara untuk semua narasi: klon ElevenLabs milik Ali. Suara sistem macOS ditolak.
- Dialog dari VEO diganti suaranya lewat speech-to-speech. Selisih durasi harus <= 0,05 detik.
- Teriakan marah: setting stabilitas rendah (~0,1) dan style tinggi (1,0), lalu dinaikkan volumenya. Satu take jarang cukup, buat 6 dan pilih.
- Nama panjang yang sulit (www.alisadikinma.com) bisa memicu filter konten VEO. Ucapkan "follow aku" saja.
- Whisper salah dengar "bongkar", "REA", "MONYET". Itu bukan bukti suaranya salah. Tetap dengarkan manusia.
- ASR setiap klip yang ada ucapan, sebelum dipakai. Kalimat yang hilang tidak kelihatan di layar.

## 3. Gambar dan klip

- gpt-image-2 (high, 2K, 9:16, dengan gambar referensi) untuk keyframe. Periksa tiap gambar ukuran penuh sebelum membuat klip.
- Tulisan di baju (bordir) harus dirender di dalam gambar. Tempelan di layar bergerak-gerak dan terlihat palsu. Sebut sisinya ("di separuh KIRI gambar") atau tulisan pindah-pindah sisi antar scene.
- Tangan: gestur yang sudah ada di frame pertama tampil dua kali (turun lalu naik lagi). Buat keyframe dengan posisi awal yang netral, lalu gestur muncul saat dibutuhkan.
- Karakter hewan (monyet) konsisten kalau referensi yang sama dipakai tiap scene.
- Adegan malam: bedakan "malam di luar" dari "ruangan gelap". Ruangan tetap terang putih, hanya langit gelap, sampai lampu dimatikan.
- Klip VEO yang ditolak dipindah ke folder arsip dengan alasan di nama file. Jangan dihapus.

## 4. Remotion (teks, kartu, efek)

- Teks bawah layar bentrok dengan subtitle karaoke. Sembunyikan teks pada y >= 1220 kecuali ditandai `keep`.
- Efek yang diminta nyata dan disukai: "Ssst!" keluar dari mulut, "WOW" saat kaget, popup follow Instagram (avatar, nama, tombol FOLLOW, kursor klik, jadi "Mengikuti"). Popup ditaruh di tengah layar.
- Label ikon (Ghidra, Decompiler) wajib ada tulisannya.
- Logo resmi (Claude Code, Codex, Cursor) langsung dipakai, jangan digambar ulang.
- Logo di benda (stiker PLN di panel MCB): hapus latar putih, pudarkan warna, tambah tekstur kasar, mode blend multiply. Tanpa itu terlihat tempelan.

## 5. Final

- Subtitle karaoke 2 kata, kata aktif berwarna. Waktu kata dari ElevenLabs untuk narasi, dari whisper untuk dialog klip (teks dari naskah).
- SFX dari library dulu. Kalau belum ada, buat lewat API sound-generation lalu simpan ke library.
- Musik di-duck di bawah suara, masuk setelah hook, keluar pelan di akhir.
- Loudness dua langkah: ukur, tambah gain ke -14 LUFS, lalu limiter (0,78). Satu langkah saja melebihi puncak setelah AAC.
- Thumbnail: sebagai cover metadata dan 4 frame pertama. Subtitle disembunyikan di frame itu (pasang subtitle dulu, lalu tempel thumbnail di atasnya).
- Watermark @alisadikinma di tengah, 12%, sepanjang video (satu baris di file subtitle ASS).

## 6. Hook dan susunan

- Tiga detik pertama menentukan. Adegan paling lucu/penasaran dipindah ke depan (lampu mati, monyet di panel MCB, teriakan), baru masuk ke isi.
- Penutup tidak perlu mengulang lelucon. Akhiri di ajakan follow.

## 7. Cara kerja dengan Ali

- Bahasa Indonesia sederhana, singkat. Catatan revisi datang per detik, kerjakan satu per satu dan laporkan satu per satu.
- Lapor jujur: yang sudah dicek (gambar, angka) dan yang belum (suara didengar manusia). Klaim yang belum terbukti ("10 menit", "game Steam") ditandai.
- Folder bersih: sembilan folder tetap (`ref keyframes clips vo shots output work _arsip .tmp`).

## 8. Alat baru di plugin (v3.13.0)

- `vidkit ingest <url> <folder>`: unduh video dari link (yt-dlp).
- `vidkit scenes <video> <folder>`: pecah per scene, simpan klip, frame awal/tengah/akhir, dan `scenes.json`.
- Skill `video-repackage`: alur dari link orang lain sampai versi Ali, dengan aturan lokalisasi Indonesia dan model gambar bawaan gpt-image-2.
