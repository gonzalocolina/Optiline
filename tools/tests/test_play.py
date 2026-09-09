from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from play import ascii_board, resolve_move, uci_to_san  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
START_LEGAL = [
    "a2a3",
    "a2a4",
    "b1a3",
    "b1c3",
    "b2b3",
    "b2b4",
    "c2c3",
    "c2c4",
    "d2d3",
    "d2d4",
    "e2e3",
    "e2e4",
    "f2f3",
    "f2f4",
    "g1f3",
    "g1h3",
    "g2g3",
    "g2g4",
    "h2h3",
    "h2h4",
]


class SanTest(unittest.TestCase):
    def test_startpos_pawn_and_knight(self) -> None:
        self.assertEqual(uci_to_san(START, "e2e4", START_LEGAL), "e4")
        self.assertEqual(uci_to_san(START, "g1f3", START_LEGAL), "Nf3")
        self.assertEqual(resolve_move("e4", START, START_LEGAL), "e2e4")
        self.assertEqual(resolve_move("Nf3", START, START_LEGAL), "g1f3")
        self.assertEqual(resolve_move("e2e4", START, START_LEGAL), "e2e4")
        self.assertEqual(resolve_move("e2-e4", START, START_LEGAL), "e2e4")

    def test_castling_and_capture(self) -> None:
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        legal = ["e1g1", "e1c1", "e1e2", "a1a8"]
        self.assertEqual(uci_to_san(fen, "e1g1", legal), "O-O")
        self.assertEqual(uci_to_san(fen, "e1c1", legal), "O-O-O")
        self.assertEqual(resolve_move("0-0", fen, legal), "e1g1")
        self.assertEqual(uci_to_san(fen, "a1a8", legal), "Rxa8")

    def test_knight_disambiguation(self) -> None:
        fen = "4k3/8/8/8/8/5N2/8/1N2K3 w - - 0 1"
        legal = ["b1d2", "f3d2", "b1c3", "e1e2"]
        self.assertEqual(uci_to_san(fen, "b1d2", legal), "Nbd2")
        self.assertEqual(uci_to_san(fen, "f3d2", legal), "Nfd2")
        self.assertEqual(resolve_move("Nbd2", fen, legal), "b1d2")
        self.assertIsNone(resolve_move("Nd2", fen, legal))

    def test_promotion(self) -> None:
        fen = "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
        legal = ["a7a8q", "a7a8n", "e1e2"]
        self.assertEqual(uci_to_san(fen, "a7a8q", legal), "a8=Q")
        self.assertEqual(resolve_move("a8=Q", fen, legal), "a7a8q")
        self.assertEqual(resolve_move("a7a8q", fen, legal), "a7a8q")

    def test_pawn_capture(self) -> None:
        fen = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"
        legal = ["e4d5", "e4e5", "g1f3"]
        self.assertEqual(uci_to_san(fen, "e4d5", legal), "exd5")
        self.assertEqual(resolve_move("exd5", fen, legal), "e4d5")

    def test_rejects_illegal(self) -> None:
        self.assertIsNone(resolve_move("e5", START, START_LEGAL))
        self.assertIsNone(resolve_move("", START, START_LEGAL))

    def test_ascii_board_has_coordinates(self) -> None:
        text = ascii_board(START, unicode_pieces=False)
        self.assertIn("r n b q k b n r", text)
        self.assertIn("R N B Q K B N R", text)
        self.assertIn("turno: blancas", text)


if __name__ == "__main__":
    unittest.main()
