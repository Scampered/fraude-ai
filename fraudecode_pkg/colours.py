"""Terminal colour helpers — works on Windows via colorama."""
try:
    import colorama; colorama.init(autoreset=False)
except ImportError:
    pass

R='\033[0m'; BOLD='\033[1m'; DIM='\033[2m'
RED='\033[91m'; GRN='\033[92m'; YLW='\033[93m'
BLU='\033[94m'; CYN='\033[96m'; WHT='\033[97m'
GRY='\033[90m'; ACC='\033[38;5;208m'

def c(t, col): return f"{col}{t}{R}"
def bold(t):   return f"{BOLD}{t}{R}"
def dim(t):    return f"{DIM}{t}{R}"
