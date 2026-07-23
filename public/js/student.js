import { ensureAnonAuth, auth } from './firebase.js';
import * as DB from './db.js';
import { $, el, toast, escapeHtml, fmtTime, shuffle, countdown } from './common.js';

let student = null;      // { id, name, schoolId, classId }
let quiz = null;         // { lesson, mode, questions, answers[], index, stopTimer }

// --------------------------------------------------- init
(async function init() {
  await ensureAnonAuth();
  const schools = await DB.listSchools();
  const sSel = $('#schoolSel');
  schools.forEach((s) => sSel.append(el('option', { value: s.id }, s.name)));
  if (schools.length) { sSel.value = schools[0].id; await loadClasses(); }
})();

async function loadClasses() {
  const cSel = $('#classSel'); cSel.innerHTML = '';
  const classes = await DB.listClasses($('#schoolSel').value);
  classes.forEach((c) => cSel.append(el('option', { value: c.id }, c.name)));
  await loadStudents();
}
async function loadStudents() {
  const stSel = $('#studentSel'); stSel.innerHTML = '';
  if (!$('#classSel').value) return;
  const students = await DB.listStudents($('#classSel').value);
  if (!students.length) { stSel.append(el('option', { value: '' }, '(Lớp chưa có học sinh)')); return; }
  students.forEach((s) => stSel.append(el('option', { value: s.id }, s.name + (s.code ? ` (${s.code})` : ''))));
}
$('#schoolSel').onchange = loadClasses;
$('#classSel').onchange = loadStudents;

$('#enterBtn').onclick = async () => {
  const sid = $('#studentSel').value;
  if (!sid) return toast('Chọn học sinh');
  student = {
    id: sid, name: $('#studentSel').selectedOptions[0].textContent,
    schoolId: $('#schoolSel').value, classId: $('#classSel').value,
  };
  $('#pickView').classList.add('hidden');
  $('#welcome').textContent = 'Xin chào, ' + student.name;
  await renderLessons();
  $('#lessonView').classList.remove('hidden');
};
$('#changeBtn').onclick = () => location.reload();

// --------------------------------------------------- lessons
async function renderLessons() {
  const box = $('#lessonCards'); box.innerHTML = '';
  const lessons = await DB.listLessons(student.classId);
  if (!lessons.length) { box.append(el('p', { class: 'muted small' }, 'Chưa có bài học cho lớp này.')); return; }
  for (const l of lessons) {
    const actions = [];
    if (l.training?.enabled)
      actions.push(el('button', { class: 'btn ok small', onclick: () => startQuiz(l, 'training') },
        `Luyện tập · ${l.training.numQuestions} câu · ${l.training.timeMinutes}′`));
    if (l.testing?.enabled)
      actions.push(el('button', { class: 'btn warn small', onclick: () => startQuiz(l, 'testing') },
        `Kiểm tra · ${l.testing.numQuestions} câu · ${l.testing.timeMinutes}′`));
    box.append(el('div', { class: 'card' },
      el('h3', {}, l.title),
      el('p', { class: 'muted small' }, l.description || ''),
      el('div', { class: 'row', style: 'margin-top:8px' }, ...actions)
    ));
  }
}

// --------------------------------------------------- quiz
async function startQuiz(lesson, mode) {
  const cfg = mode === 'testing' ? lesson.testing : lesson.training;
  let all = await DB.listQuestions(lesson.id);
  if (!all.length) return toast('Bài học chưa có câu hỏi');
  all = shuffle(all).slice(0, cfg.numQuestions);
  quiz = { lesson, mode, questions: all, answers: all.map(() => []), index: 0, stopTimer: null };

  $('#lessonView').classList.add('hidden');
  $('#resultView').classList.add('hidden');
  $('#quizView').classList.remove('hidden');
  $('#quizMode').textContent = mode === 'testing' ? 'Kiểm tra' : 'Luyện tập';
  $('#quizMode').className = 'tag ' + (mode === 'testing' ? 'amber' : 'green');
  $('#quizTitle').textContent = ' ' + lesson.title;

  const total = cfg.timeMinutes * 60;
  quiz.stopTimer = countdown(total, (r) => {
    $('#timer').textContent = fmtTime(r);
    $('#timer').classList.toggle('low', r <= 30);
  }, () => { toast('Hết giờ!'); finishQuiz(); });

  renderQuestion();
}

function renderQuestion() {
  const q = quiz.questions[quiz.index];
  const area = $('#questionArea'); area.innerHTML = '';
  area.append(el('h3', {}, `Câu ${quiz.index + 1}. `, q.text));
  const selected = quiz.answers[quiz.index];
  q.options.forEach((opt, idx) => {
    const chosen = selected.includes(idx);
    const row = el('div', { class: 'opt' + (chosen ? ' selected' : '') },
      el('span', {}, opt));
    row.onclick = () => {
      if (q.type === 'single') quiz.answers[quiz.index] = [idx];
      else {
        const arr = quiz.answers[quiz.index];
        const p = arr.indexOf(idx);
        if (p >= 0) arr.splice(p, 1); else arr.push(idx);
      }
      renderQuestion();
    };
    area.append(row);
  });
  const hint = q.type === 'multiple' ? ' (có thể chọn nhiều đáp án)' : '';
  area.append(el('p', { class: 'muted small' }, 'Loại: ' + (q.type === 'single' ? '1 đáp án đúng' : 'nhiều đáp án đúng') + hint));

  $('#counter').textContent = `${quiz.index + 1} / ${quiz.questions.length}`;
  $('#progressBar').style.width = ((quiz.index + 1) / quiz.questions.length * 100) + '%';
  $('#prevBtn').disabled = quiz.index === 0;
  $('#nextBtn').disabled = quiz.index === quiz.questions.length - 1;
}

$('#prevBtn').onclick = () => { if (quiz.index > 0) { quiz.index--; renderQuestion(); } };
$('#nextBtn').onclick = () => { if (quiz.index < quiz.questions.length - 1) { quiz.index++; renderQuestion(); } };
$('#submitBtn').onclick = () => { if (confirm('Nộp bài ngay?')) finishQuiz(); };

async function finishQuiz() {
  if (quiz.stopTimer) quiz.stopTimer();
  let correctCount = 0;
  quiz.questions.forEach((q, i) => { if (DB.isCorrect(q, quiz.answers[i])) correctCount++; });
  const total = quiz.questions.length;
  const score = Math.round((correctCount / total) * 100) / 10; // thang 10

  await DB.saveAttempt({
    uid: auth.currentUser.uid,
    studentId: student.id, studentName: student.name,
    schoolId: student.schoolId, classId: student.classId,
    lessonId: quiz.lesson.id, lessonTitle: quiz.lesson.title,
    mode: quiz.mode, total, correctCount, score,
  });

  $('#quizView').classList.add('hidden');
  $('#resultView').classList.remove('hidden');
  $('#resultMode').textContent = (quiz.mode === 'testing' ? 'Kiểm tra' : 'Luyện tập') + ' · ' + quiz.lesson.title;
  $('#resultScore').textContent = score.toFixed(1) + ' / 10';
  $('#resultDetail').innerHTML = `Trả lời đúng <b>${correctCount}/${total}</b> câu (${Math.round(correctCount / total * 100)}%).`;
  $('#reviewArea').innerHTML = '';
}

$('#backLessonsBtn').onclick = () => {
  $('#resultView').classList.add('hidden');
  $('#lessonView').classList.remove('hidden');
  renderLessons();
};
$('#reviewBtn').onclick = () => {
  const box = $('#reviewArea');
  if (box.children.length) { box.innerHTML = ''; return; }
  quiz.questions.forEach((q, i) => {
    const ok = DB.isCorrect(q, quiz.answers[i]);
    const opts = q.options.map((o, idx) => {
      let cls = 'opt';
      if (q.correct.includes(idx)) cls += ' correct';
      else if (quiz.answers[i].includes(idx)) cls += ' wrong';
      return el('div', { class: cls }, o);
    });
    box.append(el('div', { class: 'card', style: 'margin-bottom:10px' },
      el('div', {}, el('b', {}, `Câu ${i + 1}. `), q.text, ' ',
        el('span', { class: 'tag ' + (ok ? 'green' : 'amber') }, ok ? 'Đúng' : 'Sai')),
      el('div', { style: 'margin-top:8px' }, ...opts)
    ));
  });
};
