"""One chart style for the notebook figures and the dashboard.

Colours come from a CVD-validated categorical order; a given segment keeps
its colour in every chart.
"""
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#a3a29c"

SEGMENT_COLORS = {
    "Public equity": "#2a78d6",
    "Private markets": "#eb6834",
    "Fixed income": "#1baf7a",
    "Cash": "#eda100",
}
CREDIT_COLORS = {"Investment grade": "#2a78d6", "High yield": "#eb6834", "Not rated": NEUTRAL}
ACCENT = "#2a78d6"
GAIN, LOSS = "#2a78d6", "#e34948"


def use_matplotlib_style() -> None:
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
        "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 12,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "text.color": TEXT,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.axisbelow": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
        "lines.linewidth": 2, "lines.markersize": 6, "legend.frameon": False,
        "xtick.major.size": 0, "ytick.major.size": 0,
    })
