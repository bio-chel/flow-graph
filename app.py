from helpers import (
    drop_table, wrap_labels, plotnine_to_svgString_dynasize,
    remove_colname_upto_symbol, table_timestamp,
    get_discrete_cmap_colors, init_db, check_session_tables
)                    
from flask import Flask, render_template, redirect, request, jsonify, session
import pandas as pd
from io import StringIO
import sqlite3
import uuid
from datetime import timezone, datetime, timedelta
import matplotlib
matplotlib.use("Agg")
from plotnine import (
    ggplot, aes,
    geom_jitter, geom_boxplot, geom_col,
    position_jitterdodge, position_dodge,
    scale_x_discrete,
    facet_grid,
    guides, guide_legend,
    theme_classic, theme,
    element_rect, element_text, element_blank,
    scale_fill_manual
) 
import threading
import config

# Configure application
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False # Set True if using HTTPS 

# Global variables
DB_PATH = config.DATABASE_PATH
CLEANUP_INTERVAL_MINUTES = 10
last_cleanup_time = None  
cleanup_lock = threading.Lock()  # Prevents simultaneous cleanup


# Initialize table_lifetime if not exists
init_db()

@app.before_request
def cleanup_expired_tables():

    ## Check session timeout and clear if expired
    if 'last_active' in session:
        try:
            last_active = datetime.fromisoformat(session['last_active'])
            now = datetime.now(timezone.utc)
            timeout_duration = timedelta(hours=config.CLEANUP_INTERVAL) 
            
            # If session has been inactive for too long
            if now - last_active > timeout_duration:
                # Get table names before clearing session
                old_table = session.get("table_name")
                old_filtered = session.get("filtered_table")
                
                # Clear session
                session.clear()
                
                # Clean up user's tables immediately
                drop_table(old_table)
                drop_table(old_filtered)
                
                # Don't continue with global cleanup on this request
                return
        except (ValueError, TypeError):
            # If last_active is malformed, clear session
            session.clear()
            return

    global last_cleanup_time
    now = datetime.now(timezone.utc).isoformat()

    if last_cleanup_time:
        time_since_cleanup = (datetime.fromisoformat(now) - datetime.fromisoformat(last_cleanup_time)).total_seconds() / 60  # Convert to minutes
        if time_since_cleanup < CLEANUP_INTERVAL_MINUTES:
            return
        
    # Acquire lock to prevent race conditions
    if not cleanup_lock.acquire(blocking=False):
        return
    
    try: 
        last_cleanup_time = now
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Get all expired table IDs
                cur.execute("""
                    SELECT id
                    FROM table_lifetime
                    WHERE julianday(Created) < julianday('now', '-2 hours')
                """)
                
                expired_ids = [row["id"] for row in cur.fetchall()]
                
                if not expired_ids:
                    return
                
                # Drop tables for each expired ID
                for table_id in expired_ids:
                    cur.execute(f"DROP TABLE IF EXISTS {table_id}")
                
                # Remove from tracking table
                cur.executemany(
                    "DELETE FROM table_lifetime WHERE id = ?",
                    [(table_id,) for table_id in expired_ids]
                )
                
                conn.commit()
                print(f"Cleaned up {len(expired_ids)} expired tables")
                
        except sqlite3.Error as e:
            print(f"Cleanup database error: {e}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    finally:
        cleanup_lock.release()

    

@app.route('/')
def start():
    session['last_active'] = datetime.now(timezone.utc).isoformat()
    return render_template("start.html")


@app.route('/upload', methods=["GET", "POST"])
def file():
    
    if request.method == 'POST':
        session['last_active'] = datetime.now(timezone.utc).isoformat()

        # Validate file was uploaded
        try:
            infile = request.files['DataFile']
        except Exception as e:
            return render_template("start.html", error="File Request Error:" + e)
        
        # Validate filename
        if infile.filename == '':
            return render_template("start.html", error="No file selected")
        
        # Validate file type 
        if not infile.filename.lower().endswith('.csv'):
            return render_template("start.html", error="File must be a CSV")
        
        # Validate file size (e.g., 10MB limit)
        infile.seek(0, 2)  # Seek to end
        file_size = infile.tell()
        infile.seek(0)  # Reset to beginning
        
        
        if file_size > config.MAX_FILE_SIZE_BYTES:
            return render_template("start.html", 
                error=f"File too large. File size: {file_size / (1024 * 1024)} MB. Maximum size: {config.MAX_FILE_SIZE_BYTES} MB")
        
        if file_size == 0:
            return render_template("start.html", error="File is empty")
        
         # If session already had a table, delete it first
        old_table = session.get("table_name")
        drop_table(old_table)
        
        # Create a new unique table name for this user/session
        table_name = "csv_" + uuid.uuid4().hex[:8]

        # Read csv
        try:
            data = pd.read_csv(StringIO(infile.read().decode('utf-8')))
        except UnicodeDecodeError:
            return render_template("start.html", 
                error="File encoding error. Please ensure file is UTF-8 encoded")
        except pd.errors.EmptyDataError:
            return render_template("start.html", error="CSV file is empty")
        except pd.errors.ParserError as e:
            return render_template("start.html", 
                error=f"CSV parsing error: {str(e)}")
        except Exception as e:
            return render_template("start.html", 
                error=f"File read error: {str(e)}")
        
        # Validate data
        if data.empty:
            return render_template("start.html", error="File contains no data")
        if len(data.columns) < 2:
            return render_template("start.html", error="File must have at least 2 columns")

        ## Processing:
        # Convert to data frame
        dat = pd.DataFrame(data)
        # Change first column name to ID
        dat.rename(columns={dat.columns[0]: "Identifier"}, inplace=True)
        # Remove .fcs from ID column
        dat["Identifier"] = dat["Identifier"].str.replace(".fcs", "", regex=False)

        # Split IDs
        if request.form.get("split_ids") == "on":
            user_cols = request.form.get("splitID_columns")
            Split_symbol = request.form.get("splitID_separator")

            if not user_cols:
                return render_template("start.html", 
                    error="Split ID enabled but no column new names provided")
            if not Split_symbol:
                return render_template("start.html", 
                    error="Split ID enabled but no separator symbol provided")
            
            New_IdCols = [x.strip() for x in user_cols.split(",") if x.strip()]
            Number_newCols = len(New_IdCols) - 1
            
            try:
                dat[New_IdCols] = dat["Identifier"].str.split(Split_symbol, n=Number_newCols, expand=True)
            except Exception as e:
                return render_template("start.html", 
                error=f"ID Column Splitting Error: New column names must match number of splits. {str(e)}")

            # Move to beginning
            cols = ["Identifier"] + New_IdCols + [c for c in dat.columns if c not in New_IdCols + ["Identifier"]]
            dat = dat[cols]

        # Clean FlowJo export
        if request.form.get("flowjo") == "on":
            # Remove FlowJo Mean/SD last rows
            dat = dat[~dat['Identifier'].str.strip().isin(['Mean', 'SD'])]
            ## Clean-up suffix
            dat.columns = [col.replace('Freq. of ', '') for col in dat.columns]
            # Clean-up column names
            prefix_remove = request.form.get("prefix_remove")
            try:
                prefix_number = int(prefix_remove)
            except ValueError:
                prefix_number = 0 

            for i in range(prefix_number):
                dat = remove_colname_upto_symbol(dat, "/")

        
        preview = dat.head()
        colnames = dat.columns.tolist()
        
        #Add table to database
        try:
            with sqlite3.connect(DB_PATH) as conn:
                dat.to_sql(table_name, conn, index=False, if_exists="replace")
                 #Add table timestamp to table_lifetime
                table_timestamp(table_name)
                conn.commit()
        except sqlite3.Error as e:
            drop_table(table_name)  # Clean up
            return render_template("start.html", 
                error=f"Database error: {str(e)}")

        # Store metadata in the session
        session["table_name"] = table_name
        session["last_active"] = datetime.now(timezone.utc).isoformat()

        return render_template("start.html", dat = preview.to_html(index=False), colnames=colnames, dat_title="Data Frame Head")
    
    return redirect("/")


@app.route('/process_columns', methods=["POST"])
def cols():
    data = request.get_json()
    
    # Extract both lists from the received selected variables
    categorical = data.get('categorical', [])
    continuous = data.get('continuous', [])

    if not categorical or not continuous:
        return jsonify({"Error": "Must select at least 1 categorical and 1 continous variable"}), 400
    
    # Combine all columns into one list
    all_cols = categorical + continuous
    
    # Validate that we have columns
    if not all_cols:
        return jsonify({"Error": "No columns selected"}), 400
    
    original_table = session.get("table_name")
    if not original_table:
        return jsonify({"Error": "Mising table"}), 400
    
    # Delete old filtered table if present
    old_filtered = session.get("filtered_table")
    drop_table(old_filtered)
    
    # Create filtered table name
    filtered_table = "filtered_" + uuid.uuid4().hex[:8]
    
    # Convert list to comma-separated string for SQL
    columns_sql = ", ".join(f'"{c}"' for c in all_cols)
    
    # Read the data into pandas
    try:
        with sqlite3.connect(DB_PATH) as conn:
        # Select the filtered columns
            query = f"""SELECT {columns_sql} FROM {original_table}"""
            df = pd.read_sql(query, con=conn)
            
            # Melt the dataframe using categorical as id_vars
            mdf = df.melt(id_vars=categorical, var_name="Vars")
            
            # Save melted dataframe to database as filtered_table
            mdf.to_sql(filtered_table, con=conn, if_exists='replace', index=False)
            conn.commit()
    except sqlite3.Error as e:
        return jsonify({"Database Error": f"{str(e)}"}), 500
    except Exception as e:
        return jsonify({"Processing error": f"{str(e)}"}), 500
    

    table_timestamp(filtered_table)
    
    # Store filtered table and column info in session
    session["filtered_table"] = filtered_table
    session["categorical_cols"] = categorical
    session["continuous_cols"] = continuous
    session["melt_cols"] = categorical + ['Vars']
    session["last_active"] = datetime.now(timezone.utc).isoformat()
    
    return jsonify({
        "message": "Melted filtered table created",
        "categorical": categorical,
        "continuous": continuous,
        "all_columns": all_cols,
        "table": filtered_table
    })


@app.route('/graph', methods=["GET", "POST"])
def graph():

    if request.method == 'GET':
        session['last_active'] = datetime.now(timezone.utc).isoformat()

        ##Check session tables
        if not check_session_tables():
            return render_template("start.html", 
                                 error="Your session has expired. Please upload your data again.")
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                filtered_table = session.get("filtered_table")
                df = pd.read_sql(f"SELECT * FROM {filtered_table}", con=conn)
        except sqlite3.Error as e:
            return render_template("start.html", error=f"Error reading data: {str(e)}")
        
        return render_template("graph.html", table=df.to_html(index=False))

    #POST request, graph generation
    else:

        ##Check session tables
        if not check_session_tables():
            return render_template("start.html", 
                                 error="Your session has expired. Please upload your data again.")

        # Clear previous session data
        session.pop('xaxis', None)
        session.pop('frows', None)
        session.pop('fcols', None)

        # Get new selections
        xaxis = request.form.get('X_Select') or "Vars"
        frows = request.form.get('Yfacet_Select') or "."
        fcols = request.form.get('Xfacet_Select') or "."
        
        # Load table
        filtered_table = session.get("filtered_table")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                if filtered_table:
                    df = pd.read_sql(f"SELECT * FROM {filtered_table}", con=conn)
        except Exception as e:
            return render_template("graph.html", error=f"Error reading data: {str(e)}")
        
        group = request.form.get('group_Select') or "Vars"
        facet = f"{frows}~{fcols}"

        # Generate colors
        palette = request.form.get('palette')
        n_groups = df[group].nunique()
        palette_colors = get_discrete_cmap_colors(n_groups, cmap=palette)

        try:
            custom_theme = theme_classic() + theme(
                plot_background=element_rect(fill='none'),
                panel_background=element_rect(fill='none'),
                legend_background=element_rect(fill='none'),
                legend_key=element_rect(fill='none', color='none'),
                legend_text=element_text(size=8),           # Legend item text size
                legend_title=element_text(size=8),
                axis_text_x=element_text(angle=90, ha='right', size=9, color='black'),
                axis_text_y=element_text(size=9, color='black'),
                axis_title_y=element_blank()
            )

            if xaxis == 'Vars':
                custom_theme = custom_theme + theme(axis_title_x=element_blank())

            # Read the graph type button
            type = request.form.get('Graph_type')

            if type == 'Boxplot':
                graph = (ggplot(df, aes(x=xaxis, y="value", fill=group)) + 
                        geom_jitter(size=1.75, position=position_jitterdodge(jitter_width=0.1, dodge_width=0.6)) + 
                        geom_boxplot(width=0.4, alpha=0.2, color='black',
                                    position=position_dodge(width=0.6), 
                                    show_legend=False, outlier_shape='') + 
                        scale_x_discrete(limits=df[xaxis].unique(), labels=wrap_labels) + 
                        guides(fill=guide_legend(override_aes={'size': 4})) +
                        scale_fill_manual(values=palette_colors) +
                        custom_theme)
            else:
                graph = (ggplot(df, aes(x=xaxis, y="value", fill=group)) + 
                        geom_col(width=0.6, color='black',
                                    position=position_dodge(width=0.8)) + 
                        scale_x_discrete(limits=df[xaxis].unique(),labels=wrap_labels) + 
                        guides(fill=guide_legend(override_aes={'size': 0.5})) +
                        scale_fill_manual(values=palette_colors) +
                        custom_theme)

            

            # Only add facet_grid if one facet variable exists
            if frows != "." or fcols != ".":
                facet = f"{frows}~{fcols}"
                graph = graph + facet_grid(facet, scales='free')
            
            
            # Plot to custom size
            fig = plotnine_to_svgString_dynasize(p=graph, df=df, group=group, n_groups=n_groups,
                                                x_col = xaxis, 
                                                row_var=frows, 
                                                col_var=fcols)

            return render_template("graph.html", fig=fig)
        
        except Exception as e:
            return render_template("graph.html",
            table=df.to_html(index=False),
            error=f"Error generating graph: {str(e)}")

@app.route('/delete')
def delete():
    table = session.get("table_name")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            table_exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchall()
    except Exception as e:
        table_delete_message = f"No data could be found in this session. Error: {str(e)}."
                         
    if table_exists:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.execute(f"DELETE FROM table_lifetime WHERE id = ?", (table,))
                conn.commit()
                
                table_delete_message = "Uploaded Table Succesfully Deleted !"
        except Exception as e:
            table_delete_message = f"Error deleting table: {str(e)}."
    else:
        table_delete_message = "No data could be found in this session."


    filt_table = session.get("filtered_table") 
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            filttable_exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (filt_table,)).fetchall()
    except Exception as e:
        filttable_delete_message = f"No filtered data could be found in this session. Error: {str(e)}."
                         
    if filttable_exists:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(f"DROP TABLE IF EXISTS {filt_table}")
                conn.execute(f"DELETE FROM table_lifetime WHERE id = ?", (filt_table,))
                conn.commit()

                filttable_delete_message = "Filtered Table Succesfully Deleted !"
        except Exception as e:
            filttable_delete_message = f"Error deleting filtered table: {str(e)}"
    else:
        filttable_delete_message = "No filtered data could be found in this session."

    # Clear all session data
    session.clear()

    return render_template("text.html", table_delete_message=table_delete_message, filttable_delete_message=filttable_delete_message) 

@app.route('/usage')
def usage():
    return render_template("usage.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/download_plot')
def download_plot():
    
    return