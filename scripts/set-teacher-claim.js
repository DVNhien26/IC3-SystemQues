// ---------------------------------------------------------------------------
// Cấp quyền "giáo viên" (custom claim { teacher: true }) cho một tài khoản.
// Chạy bằng Node trên máy có quyền admin (KHÔNG deploy file khoá này lên web).
//
//   1. Tải service account key: Firebase Console > Project settings >
//      Service accounts > Generate new private key -> lưu là serviceAccount.json
//   2. npm install firebase-admin
//   3. node scripts/set-teacher-claim.js teacher@example.com
// ---------------------------------------------------------------------------
const admin = require('firebase-admin');
const serviceAccount = require('./serviceAccount.json');

admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

const email = process.argv[2];
if (!email) {
  console.error('Cách dùng: node scripts/set-teacher-claim.js <email>');
  process.exit(1);
}

(async () => {
  const user = await admin.auth().getUserByEmail(email);
  await admin.auth().setCustomUserClaims(user.uid, { teacher: true });
  console.log(`✅ Đã cấp quyền giáo viên cho ${email} (uid=${user.uid}).`);
  console.log('Giáo viên hãy đăng xuất & đăng nhập lại để nhận quyền mới.');
  process.exit(0);
})().catch((e) => { console.error(e); process.exit(1); });
