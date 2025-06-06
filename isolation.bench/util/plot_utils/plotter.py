import matplotlib.pyplot as plt

def set_font(size):
    text_font_size = size
    marker_font_size = size
    label_font_size = size
    axes_font_size = size

    plt.rc('pdf', use14corefonts=True, fonttype=42)
    plt.rc('ps', useafm=True)
    plt.rc('font', size=text_font_size, weight="bold", family='serif', serif='cm10')
    plt.rc('axes', labelsize=axes_font_size,labelweight="bold")    
    plt.rc('xtick', labelsize=label_font_size)    
    plt.rc('ytick', labelsize=label_font_size)    
    plt.rc('legend', fontsize=label_font_size)  

def set_standard_font():
    set_font(21)

def jains_fairness_index(l: list[float]):
    n = len(l)
    sum_l = sum(l)
    sum_squares_l = sum([ll * ll for ll in l])    
    f = (sum_l * sum_l) / (n * sum_squares_l)
    return f

# Color rules (based on https://personal.sron.nl/~pault/)
GREEN = "#117733"
TEAL  = "#44AA99"
CYAN = "#88CCEE"
OLIVE = "#999933"
SAND = "#DDCC77"
ROSE   = "#CC6677"
BLUE = "#88CCEE"
MAGENTA = "#AA4499"
GREY = GRAY = "#DDDDDD"
