"""
Runs the cube once it is online. Run with sudo: `sudo python -m main`.

For now it turns all the LED panels blue.
"""

import time

from main.matrix import create_matrix


def main() -> None:
    """
    Fills the matrix with blue and waits until interrupted.
    """
    matrix = create_matrix()
    matrix.Fill(0, 0, 255)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        matrix.Clear()


if __name__ == "__main__":
    main()
