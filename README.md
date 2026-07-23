# IC3-GS6 · Ứng dụng dạy & luyện thi

Ứng dụng web dạy học và tổ chức thi môn **IC3-GS6** cho các trường tại TP.HCM.

- **Backend:** Firebase (Firestore + Firebase Auth). Không cần máy chủ riêng.
- **Frontend:** trang tĩnh HTML/CSS/JavaScript thuần (không cần build), deploy được lên
  **Firebase Hosting**, **Cloudflare Pages**, Netlify, Vercel…

## Tính năng

| Nhóm | Chức năng |
|------|-----------|
| Quản lý | Danh sách **học sinh theo trường, theo lớp** (thêm/xoá, nhập hàng loạt) |
| Bài học & bài thi | Mỗi bài gồm **2 phần: Luyện tập (Training)** và **Kiểm tra (Testing)**; giáo viên tự đặt **số câu** và **thời gian** cho từng phần |
| Câu hỏi | Trắc nghiệm **1 đáp án** hoặc **nhiều đáp án**; trộn câu & giới hạn thời gian |
| Học sinh | Chọn trường/lớp → làm bài, có đồng hồ đếm ngược, chấm điểm, xem lại đáp án |
| Game thi đấu | Phòng chơi **thời gian thực** kiểu Wayground/Quizizz: mã PIN, bảng xếp hạng trực tiếp, tính điểm theo **đúng/sai + tốc độ** |
| Kết quả | Bảng điểm bài làm theo từng bài học |

## Cấu trúc

```
public/                 # Frontend tĩnh (thư mục deploy)
  index.html            # Trang chủ chọn vai trò
  teacher.html/.js      # Bảng điều khiển giáo viên
  student.html/.js      # Khu vực học sinh làm bài
  host.html/.js         # Điều khiển phòng thi đấu (giáo viên)
  play.html/.js         # Người chơi tham gia bằng mã PIN
  js/firebase.js        # Khởi tạo Firebase (SỬA config ở đây)
  js/db.js              # Lớp truy cập dữ liệu Firestore
  css/style.css
firebase.json           # Cấu hình Hosting + Firestore
firestore.rules         # Luật bảo mật Firestore
firestore.indexes.json  # Chỉ mục truy vấn
scripts/set-teacher-claim.js  # Cấp quyền giáo viên
```

## Thiết lập Firebase

1. Tạo project tại <https://console.firebase.google.com>.
2. **Build → Firestore Database → Create database** (chọn chế độ Production).
3. **Build → Authentication → Sign-in method**: bật **Email/Password** (cho giáo viên)
   và **Anonymous** (cho học sinh & người chơi game).
4. Tạo tài khoản giáo viên trong tab **Authentication → Users → Add user**.
5. Lấy cấu hình web: **Project settings → Your apps → Web (`</>`)**, sao chép khối
   `firebaseConfig` và dán vào `public/js/firebase.js`.

### Cấp quyền giáo viên

Luật bảo mật chỉ cho ghi dữ liệu khi tài khoản có claim `{ teacher: true }`:

```bash
cd scripts
npm install firebase-admin
# tải serviceAccount.json từ Firebase Console (Service accounts)
node set-teacher-claim.js teacher@example.com
```

Sau đó giáo viên đăng xuất/đăng nhập lại để nhận quyền.

## Deploy

### Cách 1 — Firebase Hosting
```bash
npm install -g firebase-tools
firebase login
firebase use --add            # chọn project vừa tạo (cập nhật .firebaserc)
firebase deploy --only firestore:rules,firestore:indexes,hosting
```

### Cách 2 — Cloudflare Pages / Netlify / Vercel
- **Build command:** (để trống — không cần build)
- **Output / publish directory:** `public`
- Backend vẫn là Firebase, nên chỉ cần cấu hình `firebaseConfig` là chạy được.
- Nhớ **deploy `firestore.rules` và `firestore.indexes.json`** một lần bằng
  `firebase deploy --only firestore` (hoặc dán rules trong Console).

> Ghi chú: `firebaseConfig` (apiKey…) là thông tin công khai, an toàn khi để trong
> frontend. Việc phân quyền do **Firestore Security Rules** đảm nhiệm.

## Chạy thử cục bộ

```bash
cd public
python3 -m http.server 5000
# mở http://localhost:5000
```

Hoặc dùng `firebase emulators:start` để chạy Firestore/Auth giả lập.

## Luồng sử dụng

1. Giáo viên đăng nhập `/teacher.html` → tạo **Trường → Lớp → Học sinh**.
2. Tạo **Bài học**, bật/tắt phần **Luyện tập / Kiểm tra**, đặt số câu & thời gian → thêm **Câu hỏi**.
3. Học sinh vào `/student.html` chọn lớp và làm bài.
4. Muốn thi đấu: giáo viên mở tab **🎮 Game thi đấu**, tạo phòng → nhận **mã PIN**;
   học sinh vào `/play.html` nhập PIN để chơi, bảng xếp hạng cập nhật trực tiếp.

## Mô hình dữ liệu (Firestore)

- `schools/{id}` — `{ name }`
- `classes/{id}` — `{ schoolId, name }`
- `students/{id}` — `{ schoolId, classId, name, code }`
- `lessons/{id}` — `{ schoolId, classId, title, description, training{enabled,numQuestions,timeMinutes}, testing{...} }`
- `questions/{id}` — `{ lessonId, type:'single'|'multiple', text, options[], correct[], order }`
- `attempts/{id}` — `{ uid, studentId, studentName, lessonId, mode, total, correctCount, score, finishedAt }`
- `games/{pin}` — `{ hostUid, lessonId, title, status, currentIndex, perQuestionSec, questions[], questionStartAt }`
  - `games/{pin}/players/{uid}` — `{ name, score, answeredIndex, lastCorrect, lastGain }`
