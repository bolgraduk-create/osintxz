"""
Application desktop theme.

Responsible for:

- global Qt styles

Does NOT:

- contain UI logic
- modify widgets directly
"""


from __future__ import annotations



APPLICATION_STYLE = """

QMainWindow {

    background-color: #202124;

}



QWidget {

    background-color: #202124;

    color: #ffffff;

    font-size: 14px;

}



QPushButton {

    background-color: #303134;

    border: 1px solid #5f6368;

    border-radius: 6px;

    padding: 8px;

    text-align: left;

}



QPushButton:hover {

    background-color: #3c4043;

}



QFrame {

    background-color: #292a2d;

    border-radius: 8px;

}



QLabel {

    color: #ffffff;

}

"""