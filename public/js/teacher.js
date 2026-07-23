import {
  auth, signInWithEmailAndPassword, signOut, onAuthStateChanged,
  db, doc, setDoc, serverTimestamp
} from './firebase.js';
import * as DB from './db.js';
import { $, $all, el, toast, escapeHtml, genPin } from './common.js';

let state = {
  schoolId: null, classId: null,
  editingLesson: null, editingQuestion: null,
};

// ------------------------------------------------------------------ Auth
onAuthStateChanged(auth, (user) => {
  if (user) showDashboard();
  else showLogin();
});

function showLogin() {
  $('#loginView').classList.remove('hidden');
  $('#dashView').classList.add('hidden');
  $('#logoutBtn').classList.add('hidden');
}
async function showDashboard() {
  $('#loginView').classList.add('hidden');
  $('#dashView').classList.remove('hidden');
  $('#logoutBtn').classList.remove('hidden');
  await refreshSchools();
}

$('#loginBtn').onclick = async () => {
  const email = $('#email').value.trim();
  const pass = $('#password').value;
  $('#loginErr').textContent = '';
  try {
    await signInWithEmailAndPassword(auth, email, pass);
  } catch (e) {
    $('#loginErr').textContent = 'Đăng nhập thất bại: ' + (e.code || e.message);
  }
};
$('#logoutBtn').onclick = (e) => { e.preventDefault(); signOut(auth); };

// ------------------------------------------------------------------ Tabs
$all('.tab-btn').forEach((btn) => {
  btn.onclick = () => {
    $all('.tab-btn').forEach((b) => b.classList.remove('active'));
    $all('.tab-panel').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $('#tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'lessons') renderLessons();
    if (btn.dataset.tab === 'questions') { fillLessonPickers(); renderQuestions(); }
    if (btn.dataset.tab === 'game') fillLessonPickers();
    if (btn.dataset.tab === 'reports') { fillLessonPickers(); renderReport(); }
    if (btn.dataset.tab === 'students') renderStudents();
  };
});

// ------------------------------------------------------------------ Schools & classes
async function refreshSchools() {
  const schools = await DB.listSchools();
  const picker = $('#schoolPicker');
  picker.innerHTML = '';
  schools.forEach((s) => picker.append(el('option', { value: s.id }, s.name)));
  if (schools.length) {
    if (!schools.find((s) => s.id === state.schoolId)) state.schoolId = schools[0].id;
    picker.value = state.schoolId;
  } else state.schoolId = null;
  renderSchoolList(schools);
  await refreshClasses();
}

function renderSchoolList(schools) {
  const box = $('#schoolList');
  box.innerHTML = '';
  if (!schools.length) { box.append(el('p', { class: 'muted small' }, 'Chưa có trường nào.')); return; }
  schools.forEach((s) => {
    box.append(el('div', { class: 'list-item' },
      el('span', {}, '🏫 ', s.name),
      el('button', { class: 'btn bad small', onclick: async () => {
        if (!confirm(`Xoá trường "${s.name}" và toàn bộ lớp/học sinh/bài học?`)) return;
        await DB.deleteSchool(s.id); toast('Đã xoá trường'); refreshSchools();
      } }, 'Xoá')
    ));
  });
}

$('#schoolPicker').onchange = async (e) => { state.schoolId = e.target.value; await refreshClasses(); };
$('#addSchoolBtn').onclick = async () => {
  const name = $('#newSchool').value.trim();
  if (!name) return toast('Nhập tên trường');
  await DB.addSchool(name); $('#newSchool').value = ''; toast('Đã thêm trường'); refreshSchools();
};

async function refreshClasses() {
  if (!state.schoolId) { $('#classPicker').innerHTML = ''; $('#classList').innerHTML = ''; state.classId = null; return; }
  const classes = await DB.listClasses(state.schoolId);
  const picker = $('#classPicker');
  picker.innerHTML = '';
  classes.forEach((c) => picker.append(el('option', { value: c.id }, c.name)));
  if (classes.length) {
    if (!classes.find((c) => c.id === state.classId)) state.classId = classes[0].id;
    picker.value = state.classId;
  } else state.classId = null;
  renderClassList(classes);
  renderStudents();
}

function renderClassList(classes) {
  const box = $('#classList');
  box.innerHTML = '';
  if (!classes.length) { box.append(el('p', { class: 'muted small' }, 'Chưa có lớp nào.')); return; }
  classes.forEach((c) => {
    box.append(el('div', { class: 'list-item' },
      el('span', {}, '📗 ', c.name),
      el('button', { class: 'btn bad small', onclick: async () => {
        if (!confirm(`Xoá lớp "${c.name}" và học sinh trong lớp?`)) return;
        await DB.deleteClass(c.id); toast('Đã xoá lớp'); refreshClasses();
      } }, 'Xoá')
    ));
  });
}

$('#classPicker').onchange = (e) => { state.classId = e.target.value; renderStudents(); };
$('#addClassBtn').onclick = async () => {
  if (!state.schoolId) return toast('Chọn trường trước');
  const name = $('#newClass').value.trim();
  if (!name) return toast('Nhập tên lớp');
  await DB.addClass(state.schoolId, name); $('#newClass').value = ''; toast('Đã thêm lớp'); refreshClasses();
};

// ------------------------------------------------------------------ Students
async function renderStudents() {
  const box = $('#studentList');
  box.innerHTML = '';
  if (!state.classId) { box.append(el('p', { class: 'muted small' }, 'Chọn lớp để xem học sinh.')); return; }
  const students = await DB.listStudents(state.classId);
  if (!students.length) { box.append(el('p', { class: 'muted small' }, 'Lớp chưa có học sinh.')); return; }
  const table = el('table', {},
    el('thead', {}, el('tr', {}, el('th', {}, 'Họ tên'), el('th', {}, 'Mã HS'), el('th', {}, ''))),
    el('tbody', {}, ...students.map((s) => el('tr', {},
      el('td', {}, s.name),
      el('td', {}, s.code || '—'),
      el('td', {}, el('button', { class: 'btn bad small', onclick: async () => {
        if (!confirm(`Xoá học sinh "${s.name}"?`)) return;
        await DB.deleteStudent(s.id); toast('Đã xoá'); renderStudents();
      } }, 'Xoá'))
    )))
  );
  box.append(table);
}

$('#addStudentBtn').onclick = async () => {
  if (!state.classId) return toast('Chọn lớp trước');
  const name = $('#newStudent').value.trim();
  if (!name) return toast('Nhập tên học sinh');
  await DB.addStudent(state.schoolId, state.classId, name, $('#newStudentCode').value.trim());
  $('#newStudent').value = ''; $('#newStudentCode').value = ''; toast('Đã thêm'); renderStudents();
};
$('#bulkStudentsBtn').onclick = async () => {
  if (!state.classId) return toast('Chọn lớp trước');
  const lines = $('#bulkStudents').value.split('\n').map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return toast('Chưa có tên nào');
  for (const name of lines) await DB.addStudent(state.schoolId, state.classId, name);
  $('#bulkStudents').value = ''; toast(`Đã thêm ${lines.length} học sinh`); renderStudents();
};

// ------------------------------------------------------------------ Lessons
async function renderLessons() {
  const box = $('#lessonList');
  box.innerHTML = '';
  if (!state.classId) { box.append(el('p', { class: 'muted small' }, 'Chọn trường/lớp để quản lý bài học.')); return; }
  const lessons = await DB.listLessons(state.classId);
  if (!lessons.length) { box.append(el('p', { class: 'muted small' }, 'Chưa có bài học.')); return; }
  lessons.forEach((l) => {
    const tags = [];
    if (l.training?.enabled) tags.push(el('span', { class: 'tag green' }, `Luyện tập ${l.training.numQuestions} câu · ${l.training.timeMinutes}′`));
    if (l.testing?.enabled) tags.push(el('span', { class: 'tag amber' }, `Kiểm tra ${l.testing.numQuestions} câu · ${l.testing.timeMinutes}′`));
    box.append(el('div', { class: 'list-item' },
      el('div', {},
        el('div', {}, el('b', {}, l.title)),
        el('div', { class: 'small muted' }, l.description || ''),
        el('div', { class: 'row', style: 'margin-top:6px' }, ...tags)
      ),
      el('div', { class: 'row' },
        el('button', { class: 'btn ghost small', onclick: () => editLesson(l) }, 'Sửa'),
        el('button', { class: 'btn bad small', onclick: async () => {
          if (!confirm(`Xoá bài "${l.title}" và toàn bộ câu hỏi?`)) return;
          await DB.deleteLesson(l.id); toast('Đã xoá'); renderLessons();
        } }, 'Xoá')
      )
    ));
  });
}

function editLesson(l) {
  state.editingLesson = l.id;
  $('#lessonFormTitle').textContent = 'Sửa bài học';
  $('#lessonTitle').value = l.title;
  $('#lessonDesc').value = l.description || '';
  $('#trainOn').checked = !!l.training?.enabled;
  $('#trainNum').value = l.training?.numQuestions || 10;
  $('#trainTime').value = l.training?.timeMinutes || 15;
  $('#testOn').checked = !!l.testing?.enabled;
  $('#testNum').value = l.testing?.numQuestions || 20;
  $('#testTime').value = l.testing?.timeMinutes || 30;
  $('#cancelLessonBtn').classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function resetLessonForm() {
  state.editingLesson = null;
  $('#lessonFormTitle').textContent = 'Tạo bài học / bài thi';
  $('#lessonTitle').value = ''; $('#lessonDesc').value = '';
  $('#cancelLessonBtn').classList.add('hidden');
}
$('#cancelLessonBtn').onclick = resetLessonForm;

$('#saveLessonBtn').onclick = async () => {
  if (!state.classId) return toast('Chọn trường/lớp trước');
  const title = $('#lessonTitle').value.trim();
  if (!title) return toast('Nhập tên bài');
  const data = {
    schoolId: state.schoolId, classId: state.classId, title,
    description: $('#lessonDesc').value.trim(),
    training: { enabled: $('#trainOn').checked, numQuestions: +$('#trainNum').value, timeMinutes: +$('#trainTime').value },
    testing: { enabled: $('#testOn').checked, numQuestions: +$('#testNum').value, timeMinutes: +$('#testTime').value },
  };
  if (state.editingLesson) { await DB.updateLesson(state.editingLesson, data); toast('Đã cập nhật'); }
  else { await DB.addLesson(data); toast('Đã tạo bài học'); }
  resetLessonForm(); renderLessons();
};

// ------------------------------------------------------------------ Lesson pickers (questions/game/reports)
async function fillLessonPickers() {
  if (!state.classId) return;
  const lessons = await DB.listLessons(state.classId);
  ['#qLessonPicker', '#gameLessonPicker', '#reportLessonPicker'].forEach((sel) => {
    const p = $(sel); const prev = p.value;
    p.innerHTML = '';
    lessons.forEach((l) => p.append(el('option', { value: l.id }, l.title)));
    if (lessons.find((l) => l.id === prev)) p.value = prev;
  });
}

// ------------------------------------------------------------------ Questions
function optionRow(text = '', checked = false) {
  const row = el('div', { class: 'row', style: 'margin:6px 0' },
    el('input', { type: 'checkbox', class: 'optCorrect', style: 'width:auto', ...(checked ? { checked: 'checked' } : {}) }),
    el('input', { class: 'optText', value: text, placeholder: 'Nội dung lựa chọn', style: 'flex:1' }),
    el('button', { class: 'btn bad small', type: 'button', onclick: (e) => e.target.closest('.row').remove() }, '✕')
  );
  return row;
}
function resetQuestionForm() {
  state.editingQuestion = null;
  $('#qText').value = ''; $('#qType').value = 'single';
  const box = $('#optionRows'); box.innerHTML = '';
  box.append(optionRow(), optionRow(), optionRow(), optionRow());
  $('#cancelQBtn').classList.add('hidden');
}
$('#addOptBtn').onclick = () => $('#optionRows').append(optionRow());
$('#cancelQBtn').onclick = resetQuestionForm;
$('#qLessonPicker').onchange = renderQuestions;

async function renderQuestions() {
  if (!$('#optionRows').children.length) resetQuestionForm();
  const box = $('#questionList');
  box.innerHTML = '';
  const lessonId = $('#qLessonPicker').value;
  if (!lessonId) { box.append(el('p', { class: 'muted small' }, 'Chọn bài học.')); return; }
  const qs = await DB.listQuestions(lessonId);
  if (!qs.length) { box.append(el('p', { class: 'muted small' }, 'Bài học chưa có câu hỏi.')); return; }
  qs.forEach((q, i) => {
    const opts = q.options.map((o, idx) =>
      el('li', { style: q.correct.includes(idx) ? 'color:var(--ok);font-weight:700' : '' },
        (q.correct.includes(idx) ? '✔ ' : '') + o));
    box.append(el('div', { class: 'list-item', style: 'align-items:flex-start' },
      el('div', {},
        el('div', {}, el('b', {}, `Câu ${i + 1}. `), q.text,
          ' ', el('span', { class: 'tag' }, q.type === 'single' ? '1 đáp án' : 'nhiều đáp án')),
        el('ul', { class: 'small muted', style: 'margin:6px 0 0; padding-left:18px' }, ...opts)
      ),
      el('div', { class: 'row' },
        el('button', { class: 'btn ghost small', onclick: () => editQuestion(q) }, 'Sửa'),
        el('button', { class: 'btn bad small', onclick: async () => {
          if (!confirm('Xoá câu hỏi này?')) return;
          await DB.deleteQuestion(q.id); toast('Đã xoá'); renderQuestions();
        } }, 'Xoá')
      )
    ));
  });
}

function editQuestion(q) {
  state.editingQuestion = q.id;
  $('#qText').value = q.text;
  $('#qType').value = q.type;
  const box = $('#optionRows'); box.innerHTML = '';
  q.options.forEach((o, idx) => box.append(optionRow(o, q.correct.includes(idx))));
  $('#cancelQBtn').classList.remove('hidden');
  window.scrollTo({ top: 200, behavior: 'smooth' });
}

$('#saveQBtn').onclick = async () => {
  const lessonId = $('#qLessonPicker').value;
  if (!lessonId) return toast('Chọn bài học');
  const text = $('#qText').value.trim();
  if (!text) return toast('Nhập nội dung câu hỏi');
  const rows = $all('#optionRows .row');
  const options = [], correct = [];
  rows.forEach((r, idx) => {
    const t = r.querySelector('.optText').value.trim();
    if (!t) return;
    const realIdx = options.length;
    options.push(t);
    if (r.querySelector('.optCorrect').checked) correct.push(realIdx);
  });
  if (options.length < 2) return toast('Cần ít nhất 2 lựa chọn');
  if (!correct.length) return toast('Chọn ít nhất 1 đáp án đúng');
  const type = $('#qType').value;
  if (type === 'single' && correct.length !== 1) return toast('Loại “1 đáp án” chỉ được 1 đáp án đúng');
  const data = { lessonId, type, text, options, correct, order: Date.now() };
  if (state.editingQuestion) { await DB.updateQuestion(state.editingQuestion, data); toast('Đã cập nhật'); }
  else { await DB.addQuestion(data); toast('Đã thêm câu hỏi'); }
  resetQuestionForm(); renderQuestions();
};

// ------------------------------------------------------------------ Game host
$('#createGameBtn').onclick = async () => {
  const lessonId = $('#gameLessonPicker').value;
  if (!lessonId) return toast('Chọn bài học');
  const questions = await DB.listQuestions(lessonId);
  if (questions.length < 1) return toast('Bài học chưa có câu hỏi');
  const lesson = await DB.getLesson(lessonId);
  const perQ = Math.max(5, +$('#gameQTime').value || 20);

  let pin, ok = false;
  for (let i = 0; i < 5 && !ok; i++) {
    pin = genPin();
    const ref = doc(db, 'games', pin);
    try {
      await setDoc(ref, {
        pin, hostUid: auth.currentUser.uid, lessonId, title: lesson?.title || 'Game',
        status: 'lobby', currentIndex: -1, perQuestionSec: perQ,
        // Lưu bộ câu hỏi vào doc phòng để người chơi đọc trực tiếp (kèm đáp án ẩn client chấm).
        questions: questions.map((q) => ({ text: q.text, type: q.type, options: q.options, correct: q.correct })),
        questionStartAt: null, createdAt: serverTimestamp(),
      });
      ok = true;
    } catch (e) { /* pin trùng, thử lại */ }
  }
  if (!ok) return toast('Không tạo được phòng, thử lại');
  window.location.href = `/host.html?pin=${pin}`;
};

// ------------------------------------------------------------------ Reports
$('#reportLessonPicker').onchange = renderReport;
$('#refreshReports').onclick = renderReport;

async function renderReport() {
  const box = $('#reportTable');
  box.innerHTML = '';
  const lessonId = $('#reportLessonPicker').value;
  if (!lessonId) { box.append(el('p', { class: 'muted small' }, 'Chọn bài học.')); return; }
  const attempts = await DB.listAttempts(lessonId);
  if (!attempts.length) { box.append(el('p', { class: 'muted small' }, 'Chưa có bài làm nào.')); return; }
  const table = el('table', {},
    el('thead', {}, el('tr', {},
      el('th', {}, 'Học sinh'), el('th', {}, 'Phần'), el('th', {}, 'Điểm'),
      el('th', {}, 'Đúng/Tổng'), el('th', {}, '%'), el('th', {}, 'Thời điểm'))),
    el('tbody', {}, ...attempts.map((a) => {
      const pct = a.total ? Math.round((a.correctCount / a.total) * 100) : 0;
      const when = a.finishedAt?.toDate ? a.finishedAt.toDate().toLocaleString('vi-VN') : '';
      return el('tr', {},
        el('td', {}, a.studentName || '—'),
        el('td', {}, el('span', { class: 'tag ' + (a.mode === 'testing' ? 'amber' : 'green') }, a.mode === 'testing' ? 'Kiểm tra' : 'Luyện tập')),
        el('td', {}, el('b', {}, String(a.score ?? a.correctCount))),
        el('td', {}, `${a.correctCount}/${a.total}`),
        el('td', {}, pct + '%'),
        el('td', { class: 'small muted' }, when));
    }))
  );
  box.append(table);
}

resetQuestionForm();
