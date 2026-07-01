"""Run the whole MSDN pipeline end to end, print a summary, save the figure and master."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))
import warnings; warnings.filterwarnings("ignore")
from msdn import run_pipeline, build_pipeline_figure, print_summary, export_decision_record

ASSETS, DATA = ROOT / "assets", ROOT / "data"


def main():
    state = run_pipeline()
    print_summary(state)
    build_pipeline_figure(state, ASSETS / "msdn_pipeline.png")
    state.master.to_csv(DATA / "network_decisions_sample.csv", index=False)
    export_decision_record(state, DATA / "network_decision_record.json")
    print("\nSaved assets/msdn_pipeline.png, data/network_decisions_sample.csv,")
    print("and data/network_decision_record.json (the downstream contract)")


if __name__ == "__main__":
    main()
