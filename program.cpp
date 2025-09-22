#include <iostream>
#include <vector>

using namespace std;

// Function to print the Tic-Tac-Toe board
void printBoard(const vector<char>& board) {
    cout << "-------------\n";
    for (int i = 0; i < 3; ++i) {
        cout << "| ";
        for (int j = 0; j < 3; ++j) {
            cout << board[i * 3 + j] << " | ";
        }
        cout << "\n-------------\n";
    }
}

// Function to check if a player has won
bool checkWin(const vector<char>& board, char player) {
    // Check rows, columns, and diagonals
    for (int i = 0; i < 3; ++i) {
        if ((board[i * 3] == player && board[i * 3 + 1] == player && board[i * 3 + 2] == player) ||
            (board[i] == player && board[i + 3] == player && board[i + 6] == player)) {
            return true;
        }
    }
    if ((board[0] == player && board[4] == player && board[8] == player) ||
        (board[2] == player && board[4] == player && board[6] == player)) {
        return true;
    }
    return false;
}

// Function to check if the board is full
bool checkTie(const vector<char>& board) {
    for (char cell : board) {
        if (cell == ' ') {
            return false; // There's an empty cell, so it's not a tie
        }
    }
    return true; // All cells are filled
}

int main() {
    vector<char> board(9, ' '); // Initialize the board with empty spaces
    char currentPlayer = 'X';
    bool gameWon = false;
    bool gameTied = false;

    cout << "Welcome to Tic-Tac-Toe!\n";

    while (!gameWon && !gameTied) {
        printBoard(board);

        int move;
        cout << "Player " << currentPlayer << ", enter your move (1-9): ";
        cin >> move;

        // Convert move to board index (1-9 to 0-8)
        int index = move - 1;

        // Check if the move is valid
        if (index >= 0 && index < 9 && board[index] == ' ') {
            board[index] = currentPlayer;

            // Check if the current player won
            if (checkWin(board, currentPlayer)) {
                gameWon = true;
                cout << "Player " << currentPlayer << " wins!\n";
            } else if (checkTie(board)) {
                gameTied = true;
                cout << "It's a tie!\n";
            } else {
                // Switch to the other player
                currentPlayer = (currentPlayer == 'X') ? 'O' : 'X';
            }
        } else {
            cout << "Invalid move. Try again.\n";
        }
    }

    printBoard(board);

    return 0;
}
