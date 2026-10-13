# Perbaikan media — KelolaTiktok Sandbox

- `app.py`: foto JPEG/PNG/WEBP yang diunggah di menu Post Photo/Carousel diperiksa isi aslinya, orientasi EXIF diperbaiki, dan dinormalisasi ke JPEG RGB standar; rasio tidak diubah. URL foto memakai `PUBLIC_BASE_URL` sandbox, bukan host dari reverse proxy.
- Video: metadata codec diperiksa dengan `ffprobe` jika tersedia pada server. Jika tidak terpasang, pemeriksaan dilewati (tidak ada klaim transkode otomatis). File video tidak diubah.
- Tidak mengubah kredensial, OAuth, domain, database, atau kode production.

**Penting:** TikTok mensyaratkan `PULL_FROM_URL` gambar berasal dari domain/URL prefix terverifikasi dan bisa diakses publik. Foto yang disimpan di `/tmp` pada Render dapat hilang ketika instance restart atau request dilayani instance berbeda. Untuk keandalan produksi, gunakan penyimpanan persisten yang bisa diakses publik (misalnya object storage pada domain terverifikasi). Pembaruan ini belum mengubah arsitektur penyimpanan tersebut.

**Catatan:** `ffprobe` perlu terpasang di sistem operasi Render agar pemeriksaan video aktif; dependensi Python saja tidak memasangnya. Tetap perlu uji posting dengan akun sandbox yang berizin. Audit TikTok tidak bisa dilewati lewat perubahan format media.
