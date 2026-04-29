#!/bin/bash
cd ~/ComfyUI/ComfyUI
source venv/bin/activate

# Verify Python version
echo "Using Python: $(python --version)"

# Use Metal backend for Mac
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Kill any existing ComfyUI process before starting
pkill -f "python main.py" 2>/dev/null; sleep 3

# Start ComfyUI
python main.py --listen 0.0.0.0 --port 8189
