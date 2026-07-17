# Mini Sudoku

A standalone 6x6 mini sudoku game (2x3 boxes), styled after the Nikoli/Thomas
Snyder mini sudoku app. Pure HTML/CSS/JS, no build step or dependencies.

## Run it

Open `index.html` directly in a browser, or serve the folder:

```bash
cd mini_sudoku
python3 -m http.server 8000
```

Then visit `http://localhost:8000`.

## Rules

Fill the grid so every row, column, and outlined 2x3 box contains 1-6 exactly
once. Tap/click a cell then a number to fill it in. Toggle **Notes** to pencil
in candidates, use **Hint** to reveal the correct value for the selected cell,
and **Undo**/**Erase** to correct mistakes. A new puzzle (with a freshly
generated, uniquely-solvable grid) is dealt each time the page loads, on
**New puzzle** (back arrow), or after solving.
