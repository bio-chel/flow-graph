import sqlite3
from io import StringIO
import re
from datetime import timezone, datetime
from plotnine import theme
import textwrap
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import config
from flask import session

DB_PATH = config.DATABASE_PATH

def init_db():
    ## Initialize database table
    try:
        with sqlite3.connect(config.DATABASE_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS table_lifetime (
                    id TEXT PRIMARY KEY,
                    Created TEXT NOT NULL
                )
            """)
    except sqlite3.Error as e:
        return print(f"Database error: {str(e)}")
    
def check_session_tables():
    """Check if current session has valid tables"""
    if 'table_name' not in session and 'filtered_table' not in session:
        return False
    return True

def drop_table(table_name):
    if not table_name:
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Delete table
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                    
            # Remove from tracking table
            conn.execute(f"DELETE FROM table_lifetime WHERE id = ?", (table_name,))

            conn.commit()
    except Exception as e:
        return str(e)

def wrap_labels(text, width=20):
    return [textwrap.fill(label, width=width) for label in text]

def plotnine_to_svgString_dynasize(p, df, x_col, row_var, col_var, group, n_groups,
                             base_width_per_tick = config.PLOT_BASE_WIDTH_PER_TICK,
                             min_panel_width = config.PLOT_MIN_PANEL_WIDTH,
                             min_panel_height = config.PLOT_PANEL_HEIGHT):
    
    
    # Number of X-axis ticks per panel
    if "Vars" in [x_col, row_var, col_var]:
        n_ticks = df[x_col].nunique()
    else: 
        n_ticks = df[x_col].nunique() +  df['Vars'].nunique()

    panel_width = max(min_panel_width, n_ticks * base_width_per_tick)


    if group in [x_col, row_var, col_var]:
        p = p + theme(legend_position='none')
    else:
        p = p + theme(legend_position='left')
        panel_width = panel_width + 4 + (n_groups * 0.3)

    if row_var and row_var != "." and row_var in df.columns:
        nrow = df[row_var].nunique()
    else:
        nrow = 1

    if col_var and col_var != "." and col_var in df.columns:
        ncol = df[col_var].nunique()
    else:
        ncol = 1

    # Total figure size
    fig_width = panel_width * ncol
    fig_height =(min_panel_height * nrow ) + 1



    buf = StringIO()
    p.save(buf, format="svg", width=fig_width, height= fig_height,
           limitsize=False, verbose=False, bbox_inches='tight')
    buf.seek(0)

    return buf.read()

def remove_colname_upto_symbol(df, symbol):
    escaped = re.escape(symbol)
    pattern = rf'^.*?{escaped}'
    df.columns = df.columns.str.replace(pattern, '', regex=True)
    return df

def table_timestamp(table_id):
    with sqlite3.connect(DB_PATH) as conn:
        created = datetime.now(timezone.utc).isoformat()  
        conn.execute(
            "INSERT INTO table_lifetime (id, Created) VALUES (?, ?)",
            (table_id, created)
        )
        conn.commit()

def get_discrete_cmap_colors(n_colors, cmap):
    """
    Get n discrete colors from a matplotlib colormap
    
    Args:
        n_colors: number of colors needed
        cmap: colormap name ('Accent', 'Accent_r', 'Blues', 'Blues_r', 'BrBG', 'BrBG_r',
            'BuGn', 'BuGn_r', 'BuPu', 'BuPu_r', 'CMRmap', 'CMRmap_r', 'Dark2', 'Dark2_r', 
            'GnBu', 'GnBu_r', 'Grays', 'Greens', 'Greens_r', 'Greys', 'Greys_r', 'OrRd', 
            'OrRd_r', 'Oranges', 'Oranges_r', 'PRGn', 'PRGn_r', 'Paired', 'Paired_r', 
            'Pastel1', 'Pastel1_r', 'Pastel2', 'Pastel2_r', 'PiYG', 'PiYG_r', 'PuBu', 
            'PuBuGn', 'PuBuGn_r', 'PuBu_r', 'PuOr', 'PuOr_r', 'PuRd', 'PuRd_r', 'Purples',
            'Purples_r', 'RdBu', 'RdBu_r', 'RdGy', 'RdGy_r', 'RdPu', 'RdPu_r', 'RdYlBu', 
            'RdYlBu_r', 'RdYlGn', 'RdYlGn_r', 'Reds', 'Reds_r', 'Set1', 'Set1_r', 'Set2',
            'Set2_r', 'Set3', 'Set3_r', 'Spectral', 'Spectral_r', 'Wistia', 'Wistia_r', 
            'YlGn', 'YlGnBu', 'YlGnBu_r', 'YlGn_r', 'YlOrBr', 'YlOrBr_r', 'YlOrRd', 
            'YlOrRd_r', 'afmhot', 'afmhot_r', 'autumn', 'autumn_r', 'binary', 'binary_r', 
            'bone', 'bone_r', 'brg', 'brg_r', 'bwr', 'bwr_r', 'cividis', 'cividis_r', 
            'cool', 'cool_r', 'coolwarm', 'coolwarm_r', 'copper', 'copper_r', 'cubehelix', 
            'cubehelix_r', 'flag', 'flag_r', 'gist_earth', 'gist_earth_r', 'gist_gray', 
            'gist_gray_r', 'gist_grey', 'gist_heat', 'gist_heat_r', 'gist_ncar', 'gist_ncar_r', 
            'gist_rainbow', 'gist_rainbow_r', 'gist_stern', 'gist_stern_r', 'gist_yarg', 'gist_yarg_r', 
            'gist_yerg', 'gnuplot', 'gnuplot2', 'gnuplot2_r', 'gnuplot_r', 'gray', 'gray_r', 'grey', 
            'hot', 'hot_r', 'hsv', 'hsv_r', 'inferno', 'inferno_r', 'jet', 'jet_r', 'magma', 'magma_r', 
            'nipy_spectral', 'nipy_spectral_r', 'ocean', 'ocean_r', 'pink', 'pink_r', 'plasma', 
            'plasma_r', 'prism', 'prism_r', 'rainbow', 'rainbow_r', 'seismic', 'seismic_r', 'spring', 
            'spring_r', 'summer', 'summer_r', 'tab10', 'tab10_r', 'tab20', 'tab20_r', 'tab20b', 'tab20b_r', 
            'tab20c', 'tab20c_r', 'terrain', 'terrain_r', 'turbo', 'turbo_r', 'twilight', 'twilight_r', 
            'twilight_shifted', 'twilight_shifted_r', 'viridis', 'viridis_r', 'winter', 'winter_r')
    
    Returns:
        list of hex color codes
    """
    colormap = cm.get_cmap(cmap)
    # Sample colors evenly across the colormap
    colors = [mcolors.rgb2hex(colormap(i / (n_colors - 1 if n_colors > 1 else 1))) 
              for i in range(n_colors)]
    
    return colors
