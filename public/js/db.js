// ---------------------------------------------------------------------------
// Lớp truy cập dữ liệu (data access) cho toàn app: trường, lớp, học sinh,
// bài học, câu hỏi, bài làm và game thi đấu.
// ---------------------------------------------------------------------------
import {
  db, collection, doc, getDoc, getDocs, addDoc, setDoc, updateDoc, deleteDoc,
  query, where, orderBy, onSnapshot, serverTimestamp, writeBatch
} from './firebase.js';

const snap = (s) => ({ id: s.id, ...s.data() });
const listFrom = (qs) => qs.docs.map(snap);

// ----------------------- Trường -----------------------
export async function listSchools() {
  const qs = await getDocs(query(collection(db, 'schools'), orderBy('name')));
  return listFrom(qs);
}
export async function addSchool(name) {
  return addDoc(collection(db, 'schools'), { name, createdAt: serverTimestamp() });
}
export async function deleteSchool(schoolId) {
  // Xoá cascade: lớp, học sinh, bài học, câu hỏi thuộc trường.
  const batch = writeBatch(db);
  const cols = ['classes', 'students', 'lessons'];
  for (const col of cols) {
    const qs = await getDocs(query(collection(db, col), where('schoolId', '==', schoolId)));
    qs.forEach((d) => batch.delete(d.ref));
  }
  const lessonQs = await getDocs(query(collection(db, 'lessons'), where('schoolId', '==', schoolId)));
  for (const l of lessonQs.docs) {
    const qq = await getDocs(query(collection(db, 'questions'), where('lessonId', '==', l.id)));
    qq.forEach((d) => batch.delete(d.ref));
  }
  batch.delete(doc(db, 'schools', schoolId));
  await batch.commit();
}

// ----------------------- Lớp -----------------------
export async function listClasses(schoolId) {
  const qs = await getDocs(query(collection(db, 'classes'), where('schoolId', '==', schoolId)));
  return listFrom(qs).sort((a, b) => (a.name || '').localeCompare(b.name || '', 'vi', { numeric: true }));
}
export async function addClass(schoolId, name) {
  return addDoc(collection(db, 'classes'), { schoolId, name, createdAt: serverTimestamp() });
}
export async function deleteClass(classId) {
  const batch = writeBatch(db);
  const st = await getDocs(query(collection(db, 'students'), where('classId', '==', classId)));
  st.forEach((d) => batch.delete(d.ref));
  batch.delete(doc(db, 'classes', classId));
  await batch.commit();
}

// ----------------------- Học sinh -----------------------
export async function listStudents(classId) {
  const qs = await getDocs(query(collection(db, 'students'), where('classId', '==', classId)));
  return listFrom(qs).sort((a, b) => (a.name || '').localeCompare(b.name || '', 'vi'));
}
export async function addStudent(schoolId, classId, name, code = '') {
  return addDoc(collection(db, 'students'), { schoolId, classId, name, code, createdAt: serverTimestamp() });
}
export async function deleteStudent(studentId) {
  return deleteDoc(doc(db, 'students', studentId));
}

// ----------------------- Bài học / bài thi -----------------------
// lesson: { schoolId, classId, title, description,
//           training: {enabled, numQuestions, timeMinutes},
//           testing:  {enabled, numQuestions, timeMinutes} }
export async function listLessons(classId) {
  const qs = await getDocs(query(collection(db, 'lessons'), where('classId', '==', classId)));
  return listFrom(qs).sort((a, b) => (a.title || '').localeCompare(b.title || '', 'vi'));
}
export async function getLesson(lessonId) {
  const d = await getDoc(doc(db, 'lessons', lessonId));
  return d.exists() ? snap(d) : null;
}
export async function addLesson(data) {
  return addDoc(collection(db, 'lessons'), { ...data, createdAt: serverTimestamp() });
}
export async function updateLesson(lessonId, data) {
  return updateDoc(doc(db, 'lessons', lessonId), data);
}
export async function deleteLesson(lessonId) {
  const batch = writeBatch(db);
  const qq = await getDocs(query(collection(db, 'questions'), where('lessonId', '==', lessonId)));
  qq.forEach((d) => batch.delete(d.ref));
  batch.delete(doc(db, 'lessons', lessonId));
  await batch.commit();
}

// ----------------------- Câu hỏi -----------------------
// question: { lessonId, type: 'single'|'multiple', text, options:[..],
//             correct:[indices], order }
export async function listQuestions(lessonId) {
  const qs = await getDocs(query(collection(db, 'questions'), where('lessonId', '==', lessonId)));
  return listFrom(qs).sort((a, b) => (a.order || 0) - (b.order || 0));
}
export async function addQuestion(data) {
  return addDoc(collection(db, 'questions'), { ...data, createdAt: serverTimestamp() });
}
export async function updateQuestion(qid, data) {
  return updateDoc(doc(db, 'questions', qid), data);
}
export async function deleteQuestion(qid) {
  return deleteDoc(doc(db, 'questions', qid));
}

// ----------------------- Bài làm -----------------------
export async function saveAttempt(data) {
  return addDoc(collection(db, 'attempts'), { ...data, finishedAt: serverTimestamp() });
}
export async function listAttempts(lessonId) {
  const qs = await getDocs(query(collection(db, 'attempts'), where('lessonId', '==', lessonId)));
  return listFrom(qs).sort((a, b) => (b.score || 0) - (a.score || 0));
}

/** Chấm điểm 1 câu (dùng chung cho luyện tập, kiểm tra và game). */
export function isCorrect(question, answer) {
  const correct = question.correct || [];
  const a = Array.isArray(answer) ? answer : (answer == null ? [] : [answer]);
  if (question.type === 'single') return a.length === 1 && correct.includes(a[0]);
  // multiple: đúng khi trùng khớp hoàn toàn tập đáp án.
  const sa = new Set(a), sc = new Set(correct);
  if (sa.size !== sc.size) return false;
  for (const x of sc) if (!sa.has(x)) return false;
  return true;
}
