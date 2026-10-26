import sys
from pathlib import Path

PLUGIN = Path(__file__).parents[1] / 'src/Onkyo Network Remote.indigoPlugin/Contents/Server Plugin'
sys.path.insert(0, str(PLUGIN))
