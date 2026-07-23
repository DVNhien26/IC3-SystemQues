import {
  ensureAnonAuth, auth, db, doc, getDoc, setDoc, updateDoc,
  collection, onSnapshot, serverTimestamp, increment
} from './firebase.js';
import { $, el, toast } from './common.js';

let uid = null;
let pin = null;
let game = null;
let players = [];
let myAnswer = [];          // lựa chọn hiện tại (chỉ single dùng 1 phần tử)
let answeredForIndex = -1;  // đã chốt cho câu số mấy
let qTimerId = null;

// Cho phép mở sẵn PIN qua URL: /play.html?pin=123456
const urlPin = new URLSearchParams(location.search).get('pin');
if (urlPin) $('#pinInput').value = urlPin;

(async function init() {
  const user = await ensureAnonAuth();
  uid = user.uid;
})();

$('#joinBtn').onclick = async () => {
  $('#joinErr').textContent = '';
  pin = $('#pinInput').value.trim();
  const name = $('#nameInput').value.trim();
  if (!/^\d{6}$/.test(pin)) return ($('#joinErr').textContent = 'Mã PIN gồm 6 chữ số');
  if (!name) return ($('#joinErr').textContent = 'Nhập tên hiển thị');

  const gameSnap = await getDoc(doc(db, 'games', pin));
  if (!gameSnap.exists()) return ($('#joinErr').textContent = 'Phòng không tồn tại');
  if (gameSnap.data().status === 'ended') return ($('#joinErr').textContent = 'Phòng đã kết thúc');

  // Tạo bản ghi người chơi.
  await setDoc(doc(db, 'games', pin, 'players', uid), {
    name, score: 0, answeredIndex: -1, joinedAt: serverTimestamp(),
  });

  $('#waitName').textContent = name;
  $('#waitPin').textContent = pin;
  subscribe();
};

function showOnly(id) {
  ['joinView', 'waitView', 'qView', 'fbView', 'endView'].forEach((v) =>
    $('#' + v).classList.toggle('hidden', v !== id));
}

function subscribe() {
  showOnly('waitView');
  onSnapshot(doc(db, 'games', pin), (snap) => {
    if (!snap.exists()) return;
    game = snap.data();
    render();
  });
  onSnapshot(collection(db, 'games', pin, 'players'), (qs) => {
    players = qs.docs.map((d) => ({ id: d.id, ...d.data() }));
    players.sort((a, b) => (b.score || 0) - (a.score || 0));
    if (game && (game.status === 'ended' || game.status === 'reveal')) render();
  });
}

function render() {
  if (!game) return;
  switch (game.status) {
    case 'lobby': showOnly('waitView'); break;
    case 'question': renderQuestion(); break;
    case 'reveal': renderFeedback(); break;
    case 'ended': renderEnd(); break;
  }
}

function renderQuestion() {
  const idx = game.currentIndex;
  const q = game.questions[idx];

  // Câu mới -> reset lựa chọn.
  if ($('#qView').dataset.idx != String(idx)) {
    $('#qView').dataset.idx = String(idx);
    myAnswer = [];
  }
  showOnly('qView');

  const alreadyLocked = answeredForIndex === idx;
  $('#qCounter').textContent = `Câu ${idx + 1}/${game.questions.length}`;
  $('#qText').textContent = q.text;
  $('#qHint').textContent = q.type === 'multiple' ? 'Có thể chọn nhiều đáp án, nhớ bấm “Chốt đáp án”.' : '';

  const box = $('#qOptions'); box.innerHTML = '';
  const palette = ['#ef4444', '#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899'];
  q.options.forEach((o, i) => {
    const chosen = myAnswer.includes(i);
    const row = el('div', {
      class: 'opt' + (chosen ? ' selected' : ''),
      style: `border-color:${palette[i % palette.length]}`,
    }, el('b', { style: `color:${palette[i % palette.length]}` }, String.fromCharCode(65 + i) + '. '), o);
    if (!alreadyLocked) {
      row.onclick = () => {
        if (q.type === 'single') { myAnswer = [i]; lockAnswer(); }
        else {
          const p = myAnswer.indexOf(i);
          if (p >= 0) myAnswer.splice(p, 1); else myAnswer.push(i);
          renderQuestion();
        }
      };
    }
    box.append(row);
  });

  // Nút chốt chỉ cho loại nhiều đáp án.
  const lockBtn = $('#lockBtn');
  lockBtn.classList.toggle('hidden', q.type !== 'multiple' || alreadyLocked);
  lockBtn.onclick = () => { if (myAnswer.length) lockAnswer(); };

  if (alreadyLocked) {
    box.querySelectorAll('.opt').forEach((n) => (n.style.opacity = '.6'));
    $('#qHint').textContent = 'Đã chốt! Chờ kết quả...';
  }

  // Đồng hồ đếm ngược theo server.
  if (qTimerId) clearInterval(qTimerId);
  const startMs = game.questionStartAt?.toMillis ? game.questionStartAt.toMillis() : Date.now();
  const total = game.perQuestionSec || 20;
  const tick = () => {
    const remaining = Math.max(0, total - (Date.now() - startMs) / 1000);
    $('#qTimer').textContent = Math.ceil(remaining) + 's';
    $('#qTimer').classList.toggle('low', remaining <= 5);
    if (remaining <= 0) {
      clearInterval(qTimerId);
      if (answeredForIndex !== idx) lockAnswer(true); // hết giờ, tự chốt (0đ nếu chưa chọn)
    }
  };
  tick();
  qTimerId = setInterval(tick, 250);
}

async function lockAnswer(timeout = false) {
  const idx = game.currentIndex;
  if (answeredForIndex === idx) return;
  answeredForIndex = idx;
  const q = game.questions[idx];

  // Chấm điểm phía client (phù hợp lớp học).
  const correct = isCorrect(q, myAnswer);
  const startMs = game.questionStartAt?.toMillis ? game.questionStartAt.toMillis() : Date.now();
  const total = game.perQuestionSec || 20;
  const remaining = Math.max(0, total - (Date.now() - startMs) / 1000);
  const speedFrac = total > 0 ? remaining / total : 0;
  const gained = correct ? Math.round(500 + 500 * speedFrac) : 0;

  window._lastGain = gained;
  window._lastCorrect = correct;

  try {
    await updateDoc(doc(db, 'games', pin, 'players', uid), {
      answeredIndex: idx,
      lastCorrect: correct,
      lastGain: gained,
      score: increment(gained),
    });
  } catch (e) { console.error(e); }
  renderQuestion();
}

function isCorrect(question, answer) {
  const correct = question.correct || [];
  const a = Array.isArray(answer) ? answer : [answer];
  if (question.type === 'single') return a.length === 1 && correct.includes(a[0]);
  const sa = new Set(a), sc = new Set(correct);
  if (sa.size !== sc.size) return false;
  for (const x of sc) if (!sa.has(x)) return false;
  return true;
}

function renderFeedback() {
  showOnly('fbView');
  const me = players.find((p) => p.id === uid);
  const correct = window._lastCorrect;
  $('#fbIcon').textContent = correct ? '✅' : '❌';
  $('#fbText').textContent = correct ? 'Chính xác!' : 'Chưa đúng';
  const rank = players.findIndex((p) => p.id === uid) + 1;
  $('#fbScore').innerHTML = `+${window._lastGain || 0} điểm · Tổng <b>${me?.score || 0}</b> · Hạng ${rank}/${players.length}`;
  // reset để câu sau nhận đúng trạng thái
  $('#qView').dataset.idx = '';
}

function renderEnd() {
  showOnly('endView');
  const rank = players.findIndex((p) => p.id === uid) + 1;
  const me = players.find((p) => p.id === uid);
  $('#endRank').textContent = `Hạng ${rank}/${players.length}`;
  $('#endScore').innerHTML = `Tổng điểm của em: <b>${me?.score || 0}</b>`;
  const box = $('#top3'); box.innerHTML = '';
  players.slice(0, 5).forEach((p, i) => box.append(
    el('li', {},
      el('span', { class: 'rank' }, String(i + 1)),
      el('span', {}, p.name || '?'),
      el('span', { class: 'pts' }, (p.score || 0) + ' đ'))));
}
