# KelolaTiktok — Sandbox (disinkronkan dari DashboardFYEPE Production)

Kode fitur dan antarmuka mengikuti arsip DashboardFYEPE-main(4).zip, namun **ini deployment terpisah**.

## Render sandbox
- Repository: `kelolatiktok-main` (jangan deploy ke service production)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Domain: `https://tiktok.islammoderat.my.id`
- Callback OAuth: `https://tiktok.islammoderat.my.id/auth/tiktok/callback`

## Environment variables (isi di service Render SANDBOX saja)
- `TIKTOK_CLIENT_KEY` = Client Key aplikasi TikTok sandbox
- `TIKTOK_CLIENT_SECRET` = Client Secret aplikasi TikTok sandbox
- `TIKTOK_REDIRECT_URI` = `https://tiktok.islammoderat.my.id/auth/tiktok/callback`
- `PUBLIC_BASE_URL` = `https://tiktok.islammoderat.my.id`
- `FLASK_SECRET_KEY` = secret acak khusus sandbox, konsisten antar restart
- `DATABASE_URL` = database PostgreSQL sandbox sendiri (jangan sama dengan production)
- `DATABASE_PATH` = `kelolatiktok.db` hanya bila memakai SQLite (tidak direkomendasikan untuk Render tanpa disk persisten)
- `PHOTO_UPLOAD_DIR` = direktori penyimpanan sandbox sendiri
- `TIKTOK_SCOPES` = scope yang benar-benar disetujui untuk aplikasi sandbox

**Penting:** jangan salin nilai secret atau DATABASE_URL dari DashboardFYEPE production. File ZIP ini tidak menyertakan credential.

## Perubahan
- Backend, template, role superadmin/admin_medsos, statistik, pencarian/filter, posting, dan halaman pengelolaan mengikuti versi production terlampir.
- Identitas aplikasi, database default, direktori foto, URL publik dan OAuth callback diarahkan ke sandbox.
- Berkas verifikasi TikTok memakai berkas dari ZIP KelolaTiktok sebelumnya.
- Modul `view_like_comment.html` lama tidak diaktifkan karena tidak ada di production acuan; fitur manual tersebut tidak termasuk sinkronisasi ini.

## Pengujian pascadeploy
1. Pastikan `GET /health` berhasil.
2. Login sebagai superadmin dan periksa akun serta data sandbox.
3. Uji Connect TikTok sandbox dan callback; periksa redirect URI di TikTok Developer.
4. Uji dashboard, filter, penyimpanan metadata, dan proses posting dengan akun uji.
5. Jangan menganggap sinkronisasi kode membuka pembatasan audit TikTok Direct Post; izin API tetap mengikuti status aplikasi sandbox.
