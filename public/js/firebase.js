// ---------------------------------------------------------------------------
// Khởi tạo Firebase (dùng SDK modular v10 nạp từ CDN gstatic).
// -> Thay firebaseConfig bên dưới bằng cấu hình dự án của bạn
//    (Firebase Console > Project settings > Your apps > Web app).
// ---------------------------------------------------------------------------
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import {
  getFirestore, collection, doc, getDoc, getDocs, addDoc, setDoc, updateDoc,
  deleteDoc, query, where, orderBy, onSnapshot, serverTimestamp, increment,
  writeBatch, runTransaction, limit
} from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js';
import {
  getAuth, signInAnonymously, signInWithEmailAndPassword, signOut,
  onAuthStateChanged
} from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

export const firebaseConfig = {
  apiKey: "REPLACE_ME",
  authDomain: "ic3-gs6-app.firebaseapp.com",
  projectId: "ic3-gs6-app",
  storageBucket: "ic3-gs6-app.appspot.com",
  messagingSenderId: "REPLACE_ME",
  appId: "REPLACE_ME"
};

export const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
export const auth = getAuth(app);

// Re-export các hàm Firestore/Auth hay dùng để các trang khác import gọn.
export {
  collection, doc, getDoc, getDocs, addDoc, setDoc, updateDoc, deleteDoc,
  query, where, orderBy, onSnapshot, serverTimestamp, increment, writeBatch,
  runTransaction, limit,
  signInAnonymously, signInWithEmailAndPassword, signOut, onAuthStateChanged
};

/** Đảm bảo đã đăng nhập ẩn danh (dùng cho học sinh & người chơi game). */
export function ensureAnonAuth() {
  return new Promise((resolve, reject) => {
    const unsub = onAuthStateChanged(auth, (user) => {
      unsub();
      if (user) return resolve(user);
      signInAnonymously(auth).then((cred) => resolve(cred.user)).catch(reject);
    });
  });
}
