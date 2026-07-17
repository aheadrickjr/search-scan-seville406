"use strict";

const SIZE = 6;
const BOX_ROWS = 2; // rows per box
const BOX_COLS = 3; // cols per box
const CELL_COUNT = SIZE * SIZE;

const PUZZLE_NAMES = [
  "Shelves", "Ladders", "Compass", "Lantern", "Harbor", "Meadow",
  "Ribbon", "Anchor", "Beacon", "Orchard", "Trellis", "Pinwheel",
];

function boxIndex(row, col) {
  return Math.floor(row / BOX_ROWS) * (SIZE / BOX_COLS) + Math.floor(col / BOX_COLS);
}

function shuffled(array) {
  const a = array.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// --- Solver / generator ------------------------------------------------

function canPlace(grid, row, col, value) {
  for (let c = 0; c < SIZE; c++) if (grid[row][c] === value) return false;
  for (let r = 0; r < SIZE; r++) if (grid[r][col] === value) return false;
  const boxR = Math.floor(row / BOX_ROWS) * BOX_ROWS;
  const boxC = Math.floor(col / BOX_COLS) * BOX_COLS;
  for (let r = boxR; r < boxR + BOX_ROWS; r++) {
    for (let c = boxC; c < boxC + BOX_COLS; c++) {
      if (grid[r][c] === value) return false;
    }
  }
  return true;
}

function findEmptyCell(grid) {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (grid[r][c] === 0) return [r, c];
    }
  }
  return null;
}

function fillRandomSolution(grid) {
  const spot = findEmptyCell(grid);
  if (!spot) return true;
  const [row, col] = spot;
  for (const value of shuffled([1, 2, 3, 4, 5, 6])) {
    if (canPlace(grid, row, col, value)) {
      grid[row][col] = value;
      if (fillRandomSolution(grid)) return true;
      grid[row][col] = 0;
    }
  }
  return false;
}

function makeSolvedGrid() {
  const grid = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
  fillRandomSolution(grid);
  return grid;
}

// Counts solutions up to `limit`, stopping early once reached.
function countSolutions(grid, limit) {
  const spot = findEmptyCell(grid);
  if (!spot) return 1;
  const [row, col] = spot;
  let count = 0;
  for (let value = 1; value <= SIZE; value++) {
    if (canPlace(grid, row, col, value)) {
      grid[row][col] = value;
      count += countSolutions(grid, limit - count);
      grid[row][col] = 0;
      if (count >= limit) break;
    }
  }
  return count;
}

function generatePuzzle(minClues = 14) {
  const solution = makeSolvedGrid();
  const puzzle = solution.map((row) => row.slice());
  const positions = shuffled(
    Array.from({ length: CELL_COUNT }, (_, i) => [Math.floor(i / SIZE), i % SIZE])
  );

  let clues = CELL_COUNT;
  for (const [row, col] of positions) {
    if (clues <= minClues) break;
    const backup = puzzle[row][col];
    puzzle[row][col] = 0;
    const trial = puzzle.map((r) => r.slice());
    if (countSolutions(trial, 2) === 1) {
      clues -= 1;
    } else {
      puzzle[row][col] = backup;
    }
  }
  return { puzzle, solution };
}

// --- Game state ----------------------------------------------------------

const state = {
  solution: null,
  givens: null, // boolean grid, true = pre-filled clue (immutable)
  values: null, // number grid, 0 = empty
  notes: null, // Set per cell
  selected: null, // [row, col]
  notesMode: false,
  history: [], // stack of {row, col, prevValue, prevNotes}
  seconds: 0,
  timerId: null,
  solved: false,
  puzzleId: 1,
  puzzleName: "Random",
};

function emptyNotesGrid() {
  return Array.from({ length: SIZE }, () => Array.from({ length: SIZE }, () => new Set()));
}

function newGame() {
  const { puzzle, solution } = generatePuzzle(14);
  state.solution = solution;
  state.givens = puzzle.map((row) => row.map((v) => v !== 0));
  state.values = puzzle.map((row) => row.slice());
  state.notes = emptyNotesGrid();
  state.selected = null;
  state.notesMode = false;
  state.history = [];
  state.seconds = 0;
  state.solved = false;
  state.puzzleId = Math.floor(100 + Math.random() * 900);
  state.puzzleName = PUZZLE_NAMES[Math.floor(Math.random() * PUZZLE_NAMES.length)];

  document.getElementById("puzzle-id").textContent = state.puzzleId;
  document.getElementById("puzzle-name").textContent = state.puzzleName;
  document.getElementById("notes-btn").classList.remove("active");
  document.getElementById("notes-state").textContent = "OFF";
  document.getElementById("results-btn").disabled = false;

  restartTimer();
  render();
}

function resetProgress() {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (!state.givens[r][c]) {
        state.values[r][c] = 0;
        state.notes[r][c].clear();
      }
    }
  }
  state.history = [];
  state.solved = false;
  document.getElementById("results-btn").disabled = false;
  restartTimer();
  render();
}

function restartTimer() {
  if (state.timerId) clearInterval(state.timerId);
  state.seconds = 0;
  updateTimerDisplay();
  state.timerId = setInterval(() => {
    state.seconds += 1;
    updateTimerDisplay();
  }, 1000);
}

function stopTimer() {
  if (state.timerId) clearInterval(state.timerId);
  state.timerId = null;
}

function updateTimerDisplay() {
  const m = Math.floor(state.seconds / 60);
  const s = state.seconds % 60;
  document.getElementById("timer").textContent = `${m}:${String(s).padStart(2, "0")}`;
}

// --- Rendering -------------------------------------------------------------

const boardEl = document.getElementById("board");

function render() {
  boardEl.innerHTML = "";
  const [selRow, selCol] = state.selected || [-1, -1];
  const selectedValue = selRow >= 0 ? state.values[selRow][selCol] : 0;

  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.dataset.row = r;
      cell.dataset.col = c;

      if (state.givens[r][c]) cell.classList.add("given");
      if ((c + 1) % BOX_COLS === 0 && c !== SIZE - 1) cell.classList.add("box-right");
      if ((r + 1) % BOX_ROWS === 0 && r !== SIZE - 1) cell.classList.add("box-bottom");

      const isSelected = r === selRow && c === selCol;
      const isPeer =
        selRow >= 0 &&
        (r === selRow || c === selCol || boxIndex(r, c) === boxIndex(selRow, selCol));

      if (isSelected) cell.classList.add("selected");
      else if (isPeer) cell.classList.add("peer");

      const value = state.values[r][c];
      if (value !== 0) {
        if (selectedValue !== 0 && value === selectedValue && !isSelected) {
          cell.classList.add("same-value");
        }
        if (!state.givens[r][c] && value !== state.solution[r][c]) {
          cell.classList.add("error");
        }
        cell.textContent = value;
      } else if (state.notes[r][c].size > 0) {
        const notesWrap = document.createElement("div");
        notesWrap.className = "notes";
        for (let n = 1; n <= SIZE; n++) {
          const span = document.createElement("span");
          span.textContent = state.notes[r][c].has(n) ? n : "";
          notesWrap.appendChild(span);
        }
        cell.appendChild(notesWrap);
      }

      cell.addEventListener("click", () => selectCell(r, c));
      boardEl.appendChild(cell);
    }
  }
}

// --- Interaction -----------------------------------------------------------

function selectCell(row, col) {
  state.selected = [row, col];
  render();
}

function pushHistory(row, col) {
  state.history.push({
    row,
    col,
    prevValue: state.values[row][col],
    prevNotes: new Set(state.notes[row][col]),
  });
}

function enterNumber(num) {
  if (!state.selected || state.solved) return;
  const [row, col] = state.selected;
  if (state.givens[row][col]) return;

  pushHistory(row, col);

  if (state.notesMode) {
    const cellNotes = state.notes[row][col];
    if (cellNotes.has(num)) cellNotes.delete(num);
    else cellNotes.add(num);
  } else {
    state.values[row][col] = state.values[row][col] === num ? 0 : num;
    state.notes[row][col].clear();
  }

  render();
  checkWin();
}

function eraseCell() {
  if (!state.selected || state.solved) return;
  const [row, col] = state.selected;
  if (state.givens[row][col]) return;
  if (state.values[row][col] === 0 && state.notes[row][col].size === 0) return;

  pushHistory(row, col);
  state.values[row][col] = 0;
  state.notes[row][col].clear();
  render();
}

function undo() {
  const last = state.history.pop();
  if (!last) return;
  state.values[last.row][last.col] = last.prevValue;
  state.notes[last.row][last.col] = last.prevNotes;
  state.solved = false;
  render();
}

function giveHint() {
  if (state.solved) return;
  let target = state.selected;
  if (!target || state.givens[target[0]][target[1]] || state.values[target[0]][target[1]] === state.solution[target[0]][target[1]]) {
    target = null;
    for (let r = 0; r < SIZE && !target; r++) {
      for (let c = 0; c < SIZE && !target; c++) {
        if (!state.givens[r][c] && state.values[r][c] !== state.solution[r][c]) {
          target = [r, c];
        }
      }
    }
  }
  if (!target) return;

  const [row, col] = target;
  pushHistory(row, col);
  state.values[row][col] = state.solution[row][col];
  state.notes[row][col].clear();
  state.selected = target;
  render();
  checkWin();
}

function toggleNotes() {
  state.notesMode = !state.notesMode;
  document.getElementById("notes-btn").classList.toggle("active", state.notesMode);
  document.getElementById("notes-state").textContent = state.notesMode ? "ON" : "OFF";
}

function isComplete() {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (state.values[r][c] === 0) return false;
    }
  }
  return true;
}

function isCorrect() {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (state.values[r][c] !== state.solution[r][c]) return false;
    }
  }
  return true;
}

function checkWin() {
  if (isComplete() && isCorrect()) {
    state.solved = true;
    stopTimer();
    document.getElementById("results-btn").disabled = true;
    showWinModal();
  }
}

function showWinModal() {
  document.getElementById("modal-time").textContent = document.getElementById("timer").textContent;
  document.getElementById("modal").classList.remove("hidden");
}

// --- Wiring ------------------------------------------------------------

document.getElementById("keypad").addEventListener("click", (e) => {
  const key = e.target.closest(".key");
  if (!key) return;
  if (key.dataset.num) enterNumber(Number(key.dataset.num));
});

document.getElementById("erase-btn").addEventListener("click", eraseCell);
document.getElementById("undo-btn").addEventListener("click", undo);
document.getElementById("hint-btn").addEventListener("click", giveHint);
document.getElementById("notes-btn").addEventListener("click", toggleNotes);
document.getElementById("reset-btn").addEventListener("click", resetProgress);
document.getElementById("back-btn").addEventListener("click", newGame);

document.getElementById("results-btn").addEventListener("click", () => {
  if (isComplete() && isCorrect()) {
    state.solved = true;
    stopTimer();
    showWinModal();
  } else {
    render();
    boardEl.classList.add("shake");
    setTimeout(() => boardEl.classList.remove("shake"), 300);
  }
});

document.getElementById("modal-close").addEventListener("click", () => {
  document.getElementById("modal").classList.add("hidden");
  newGame();
});

document.getElementById("help-btn").addEventListener("click", () => {
  document.getElementById("help-modal").classList.remove("hidden");
});
document.getElementById("help-close").addEventListener("click", () => {
  document.getElementById("help-modal").classList.add("hidden");
});

document.addEventListener("keydown", (e) => {
  if (!state.selected) return;
  const [row, col] = state.selected;

  if (e.key >= "1" && e.key <= "6") {
    enterNumber(Number(e.key));
  } else if (e.key === "Backspace" || e.key === "Delete" || e.key === "0") {
    eraseCell();
  } else if (e.key === "ArrowUp") {
    state.selected = [(row + SIZE - 1) % SIZE, col];
    render();
  } else if (e.key === "ArrowDown") {
    state.selected = [(row + 1) % SIZE, col];
    render();
  } else if (e.key === "ArrowLeft") {
    state.selected = [row, (col + SIZE - 1) % SIZE];
    render();
  } else if (e.key === "ArrowRight") {
    state.selected = [row, (col + 1) % SIZE];
    render();
  }
});

newGame();
