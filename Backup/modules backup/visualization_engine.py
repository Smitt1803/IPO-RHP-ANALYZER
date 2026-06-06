import plotly.express as px
import os

# Auto-detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_visuals(df):

    visuals_folder = os.path.join(BASE_DIR, "outputs", "visuals")
    os.makedirs(visuals_folder, exist_ok=True)

    fig = px.bar(df, y="composite_score")

    output_path = os.path.join(visuals_folder, "composite_score.png")
    fig.write_image(output_path)
