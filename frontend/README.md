# Auto Tool Frontend

React + TypeScript + Vite + TailwindCSS UI cho backend Auto Tool local.

## Chay Local

Chay backend API truoc:

```powershell
cd backend
py -m uvicorn app.main:app --reload --port 8000
```

Chay frontend:

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Mac dinh frontend goi API tai:

```txt
VITE_API_BASE_URL=http://localhost:8000
```

Neu backend chay cong khac, sua `.env` roi restart `npm run dev`.

Khi frontend duoc build va serve chung voi backend launcher/exe, app se goi API cung origin nen khong can `VITE_API_BASE_URL`.

## Luong Su Dung

1. Tao project va nhap folder path local.
2. Nhap danh sach Gemini API key, moi dong mot key.
3. Chon preset hoac chinh slider render.
4. Scan videos de kiem tra input.
5. Render preview de tao 1 video ngan toi da 8 giay.
6. Xem preview, sua script/subtitle neu can, bam Save Script.
7. Render full batch. Neu da luu custom script, backend se dung script do cho batch.
8. Xem ket qua va copy path output.
