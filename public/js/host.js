import {
  auth, onAuthStateChanged, db, doc, getDoc, updateDoc, deleteDoc,
  collection, onSnapshot, serverTimestamp
} from './firebase.js';
import { $, el, toast, fmtTime } from './common.js';

const pin = new URLSearchParams(location.search).get('pin');
let game = null;          // dữ liệu doc phòng
let players = [];         // danh sách người chơi (realtime)
let qTimerId = null;

if (!pin) { document.body.innerHTML = '<p style="padding:40px">Thiếu mã phòng.</p>'; }

$('#joinUrl').textContent = location.origin + '/play.html';
$('#pinDisplay').textContent = pin;

onAuthStateChanged(auth, (user) => {
  if (!user) { showOnly('noAuthView'); return; }
  subscribe();
});

function showOnly(id) {
  ['lobbyView', 'qView', 'boardView', 'endView', 'noAuthView'].forEach((v) =>
    $('#' + v).classList.toggle('hidden', v !== id));
}

function subscribe() {
  // Lắng nghe doc phòng
  onSnapshot(doc(db, 'games', pin), (snap) => {
    if (!snap.exists()) { document.body.innerHTML = '<p style="padding:40px">Phòng không tồn tại.</p>'; return; }
    game = snap.data();
    render();
  });
  // Lắng nghe người chơi
  onSnapshot(collection(db, 'games', pin, 'players'), (qs) => {
    players = qs.docs.map((d) => ({ id: d.id, ...d.data() }));
    players.sort((a, b) => (b.score || 0) - (a.score || 0));
    render();
  });
}

function render() {
  if (!game) return;
  $('#gameTitle').textContent = game.title || '';
  if (game.status === 'lobby') {
    showOnly('lobbyView');
    $('#lobbyCount').textContent = players.length + ' người chơi';
    const box = $('#lobbyPlayers'); box.innerHTML = '';
    players.forEach((p) => box.append(el('li', {}, el('span', { class: 'rank' }, '🙂'), p.name || '?')));
    $('#startBtn').disabled = players.length === 0;
  } else if (game.status === 'question') {
    renderQuestion();
  } else if (game.status === 'reveal') {
    renderBoard(false);
  } else if (game.status === 'ended') {
    renderBoard(true);
  }
}

function renderQuestion() {
  showOnly('qView');
  const q = game.questions[game.currentIndex];
  $('#qCounter').textContent = `Câu ${game.currentIndex + 1}/${game.questions.length}`;
  $('#qText').textContent = q.text;
  const box = $('#qOptions'); box.innerHTML = '';
  const palette = ['#ef4444', '#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899'];
  q.options.forEach((o, i) => box.append(
    el('div', { class: 'opt', style: `border-color:${palette[i % palette.length]}` },
      el('b', { style: `color:${palette[i % palette.length]}` }, String.fromCharCode(65 + i) + '. '), o)));

  const answered = players.filter((p) => p.answeredIndex === game.currentIndex).length;
  $('#answerCount').textContent = `${answered}/${players.length} đã trả lời`;

  // Đồng hồ đếm ngược dựa trên questionStartAt của server.
  if (qTimerId) clearInterval(qTimerId);
  const startMs = game.questionStartAt?.toMillis ? game.questionStartAt.toMillis() : Date.now();
  const total = game.perQuestionSec || 20;
  const tick = () => {
    const remaining = Math.max(0, total - (Date.now() - startMs) / 1000);
    $('#qTimer').textContent = Math.ceil(remaining) + 's';
    $('#qTimer').classList.toggle('low', remaining <= 5);
    // Tự động mở đáp án khi hết giờ hoặc mọi người đã trả lời.
    const allAnswered = players.length > 0 && players.every((p) => p.answeredIndex === game.currentIndex);
    if (remaining <= 0 || allAnswered) { clearInterval(qTimerId); }
  };
  tick();
  qTimerId = setInterval(tick, 250);
}

function renderBoard(isFinal) {
  showOnly(isFinal ? 'endView' : 'boardView');
  const listId = isFinal ? '#finalList' : '#leaderList';
  const box = $(listId); box.innerHTML = '';
  players.slice(0, 20).forEach((p, i) => box.append(
    el('li', {},
      el('span', { class: 'rank' }, String(i + 1)),
      el('span', {}, p.name || '?'),
      el('span', { class: 'pts' }, (p.score || 0) + ' đ'))));
  if (!isFinal) {
    $('#boardTitle').textContent = game.currentIndex + 1 >= game.questions.length
      ? 'Bảng xếp hạng (câu cuối)' : 'Bảng xếp hạng';
    $('#nextBtn').textContent = game.currentIndex + 1 >= game.questions.length ? '🏁 Kết thúc' : 'Câu tiếp theo →';
  }
}

// ------------------ Điều khiển ------------------
$('#startBtn').onclick = async () => {
  await updateDoc(doc(db, 'games', pin), {
    status: 'question', currentIndex: 0, questionStartAt: serverTimestamp(),
  });
};
$('#revealBtn').onclick = async () => {
  await updateDoc(doc(db, 'games', pin), { status: 'reveal' });
};
$('#nextBtn').onclick = async () => {
  const next = game.currentIndex + 1;
  if (next >= game.questions.length) {
    await updateDoc(doc(db, 'games', pin), { status: 'ended' });
  } else {
    await updateDoc(doc(db, 'games', pin), {
      status: 'question', currentIndex: next, questionStartAt: serverTimestamp(),
    });
  }
};
