#!/bin/bash
uv run --with playwright --with imageio-ffmpeg --with requests --with tqdm seattle_parks_video.py "$1" "$2" ${3:+-o "$3"}
