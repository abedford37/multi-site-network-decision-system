"""Run the whole MSDN pipeline end to end, print a summary, save the figure and master."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))
import warnings; warnings.filterwarnings("ignore")
from msdn import run_pipeline, build_pipeline_figure, print_summary

ASSETS, DATA = ROOT / "assets", ROOT / "data"


def main():
    state = run_pipeline()
    print_summary(state)
    build_pipeline_figure(state, ASSETS / "msdn_pipeline.png")
    state.master.to_csv(DATA / "network_decisions_sample.csv", index=False)
    print("\nSaved assets/msdn_pipeline.png and data/network_decisions_sample.csv")


if __name__ == "__main__":
    main()
