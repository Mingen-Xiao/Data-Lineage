# Import
from enum import auto
import os
from turtle import width
import visdcc
import base64
import pandas as pd
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd

# Constants
# default node and edge size
DEFAULT_NODE_SIZE = 7
DEFAULT_EDGE_SIZE = 1

# default node and egde color
DEFAULT_COLOR = '#97C2FC'

# Taken from https://stackoverflow.com/questions/470690/how-to-automatically-generate-n-distinct-colors
KELLY_COLORS_HEX = [
    "#FFB300", # Vivid Yellow
    "#803E75", # Strong Purple
    "#FF6800", # Vivid Orange
    "#A6BDD7", # Very Light Blue
    "#C10020", # Vivid Red
    "#CEA262", # Grayish Yellow
    "#817066", # Medium Gray

    # The following don't work well for people with defective color vision
    "#007D34", # Vivid Green
    "#F6768E", # Strong Purplish Pink
    "#00538A", # Strong Blue
    "#FF7A5C", # Strong Yellowish Pink
    "#53377A", # Strong Violet
    "#FF8E00", # Vivid Orange Yellow
    "#B32851", # Strong Purplish Red
    "#F4C800", # Vivid Greenish Yellow
    "#7F180D", # Strong Reddish Brown
    "#93AA00", # Vivid Yellowish Green
    "#593315", # Deep Yellowish Brown
    "#F13A13", # Vivid Reddish Orange
    "#232C16", # Dark Olive Green
    ]

DEFAULT_OPTIONS = {
    'height': '1000px',
    'width': '100%',
    'interaction':{'hover': True},
    # 'edges': {'scaling': {'min': 1, 'max': 5}},
    'physics': False
}

# edit the size
CONTENT_STYLE = {
    "margin-left": "18rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}

# Code
def get_options(directed, opts_args):
    opts = DEFAULT_OPTIONS.copy()
    opts['edges'] = { 'arrows': { 'to': directed } }
    if opts_args is not None:
        opts.update(opts_args)
    return opts

def get_distinct_colors(n):
    """Return distict colors, currently atmost 20

    Parameters
    -----------
    n: int
        the distinct colors required
    """
    if n <= 20:
        return KELLY_COLORS_HEX[:n]

def create_card(id, value, description):
    """Creates card for high level stats

    Parameters
    ---------------
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.H4(id=id, children=value, className='card-title'),
                html.P(children=description),
            ]))

def create_color_legend(text, color):
    """Individual row for the color legend
    """
    return create_row([
        html.Div(style={'width': '10px', 'height': '10px', 'background-color': color}),
        html.Div(text, style={'padding-left': '10px'}),
    ])

def fetch_flex_row_style():
    return {'display': 'flex', 'flex-direction': 'row', 'justify-content': 'flex-start', 'align-items': 'center'}

def create_row(children, style=fetch_flex_row_style()):
    return dbc.Row(children,
                   style=style,
                   className="column flex-display")

search_form = dbc.FormGroup(
    [
        dbc.Input(type="search", id="search_graph", placeholder="Search node in graph..."),
        dbc.FormText(
            "Show the node you are looking for",
            color="secondary",
        ),
    ]
)

filter_node_form = dbc.FormGroup([
    dbc.Textarea(id="filter_nodes", placeholder="Enter filter node query here..."),
    dbc.FormText(
        html.P([
            "Filter on nodes properties by using ",
            html.A("Pandas Query syntax",
            href="https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html"),
        ]),
        color="secondary",
    ),
])
    
filter_edge_form = dbc.FormGroup([
    dbc.Textarea(id="filter_edges", placeholder="Enter filter edge query here..."),
    dbc.FormText(
        html.P([
            "Filter on edges properties by using ",
            html.A("Pandas Query syntax",
            href="https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.query.html"),
        ]),
        color="secondary",
    ),
])

def get_select_form_layout(id, options, label, description):
    """Creates a select (dropdown) form with provides details

    Parameters
    -----------
    id: str
        id of the form
    options: list
        options to show
    label: str
        label of the select dropdown bar
    description: str
        long text detail of the setting
    """
    return  dbc.FormGroup([
                dbc.InputGroup([
                    dbc.InputGroupAddon(label, addon_type="append"),
                    dbc.Select(id=id,
                        options=options
                    ),]),
                dbc.FormText(description, color="secondary",)
            ,])

def get_categorical_features(df_, unique_limit=20, blacklist_features=['shape', 'label', 'id']):
    """Identify categorical features for edge or node data and return their names
    Additional logics: (1) cardinality should be within `unique_limit`, (2) remove blacklist_features
    """
    # identify the rel cols + None
    cat_features = ['None'] + df_.columns[(df_.dtypes == 'object') & (df_.apply(pd.Series.nunique) <= unique_limit)].tolist()
    # remove irrelevant cols
    try:
        for col in blacklist_features:
            cat_features.remove(col)
    except:
        pass
    # return
    return cat_features

def get_numerical_features(df_, unique_limit=20):
    """Identify numerical features for edge or node data and return their names
    """
    # supported numerical cols
    numerics = ['int16', 'int32', 'int64', 'float16', 'float32', 'float64']
    # identify numerical features
    numeric_features = ['None'] + df_.select_dtypes(include=numerics).columns.tolist()
    # remove blacklist cols (for nodes)
    try:
        numeric_features.remove('size')
    except:
        pass
    # return
    return numeric_features

def get_app_layout(graph_data, color_legends=[], directed=False, vis_opts=None):
    """Create and return the layout of the app

    Parameters
    --------------
    graph_data: dict{nodes, edges}
        network data in format of visdcc
    """
    # Step 1-2: find categorical features of nodes and edges
    cat_node_features = get_categorical_features(pd.DataFrame(graph_data['nodes']), 20, ['shape', 'label', 'id'])
    cat_edge_features = get_categorical_features(pd.DataFrame(graph_data['edges']).drop(columns=['color']), 20, ['color', 'from', 'to', 'id'])
    # Step 3-4: Get numerical features of nodes and edges
    num_node_features = get_numerical_features(pd.DataFrame(graph_data['nodes']))
    num_edge_features = get_numerical_features(pd.DataFrame(graph_data['edges']))
    # Create new function of selecting nodes

    # Step 5: create and return the layout
    # resolve path
    this_dir, _ = os.path.split(__file__)
    # styling the sidebar
    SIDEBAR_STYLE = {
        # "display": "flex",
        "position": "absolute",
        # 'justify-content': 'center', 
        # 'align-items': 'center',
        "top": 0,
        "left": 0,
        # "bottom": 0,
        "height": "200",
        "width": "16rem",
        "padding": "2rem 1rem",
        "background-color": "#f8f9fa"
    }
    side_bar = html.Div([
            # create_row([
                # dbc.Col([
                    # setting panel
                    # dbc.Form([
                        html.H3("Data Discovery Tool",  className="display-6"),
                        html.Hr(),
                        
                        # ---- Navigation testing section ----
                        # create_row([
                            html.H6("Navigation"), # heading
                            html.Hr(className="my-2"),
                            # ],    {**fetch_flex_row_style(), 'margin-left': 0, 'margin-right':0, 'justify-content': 'space-between'}),
                        dbc.Nav(
                            [
                                dbc.NavLink("Data flow map", href="/", active="exact"),
                                dbc.NavLink("Subquery", href="/page-1", active="exact"),
                                dbc.NavLink("Case statement", href="/page-2", active="exact"),
                                dbc.NavLink("Data catalog", href="/page-3", active="exact"),
                            ],
                            vertical=True,
                            pills=True
                        ),
                        # highlight the button
                        dcc.Location(id="url"),
                        # sidebar,
                        # content
                        
                        # ---- upload section ----
                        html.H6("Upload file"),
                        html.Hr(className="my-2"),
                        # dbc.Input(id="csvfile", type="file"),
                        dcc.Upload(
                            id='upload-data',
                            children=html.Div([
                                'Upload node and edge file'
                            ]),
                            style={
                                'width': '100%',
                                'height': '60px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'solid',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'margin': '10px'
                            },
                            multiple=True
                            ),

                        dcc.Upload(
                            id='upload-sql-data',
                            children=html.Div([
                                'Upload sqlscripts'
                            ]),
                            style={
                                'width': '100%',
                                'height': '60px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'solid',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'margin': '10px'
                            },
                            multiple=True
                            ),  

                        dcc.Upload(
                            id='upload-catalog-data',
                            children=html.Div([
                                'Upload data catalog'
                            ]),
                            style={
                                'width': '100%',
                                'height': '60px',
                                'lineHeight': '60px',
                                'borderWidth': '2px',
                                'borderStyle': 'solid',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'margin': '10px'
                            },
                            multiple=True
                            ),    
                                                                                            
                        # ---- search section ----
                        html.H6("Search"),
                        html.Hr(className="my-2"),
                        search_form,
                        
                        # ---- filter section ----
                        # create_row([
                            html.H6("Filter"),
                            dbc.Button("Hide/Show", id="filter-show-toggle-button", outline=True, color="secondary", size="sm"), # legend
                        # ], {**fetch_flex_row_style(), 'margin-left': 0, 'margin-right':0, 'justify-content': 'space-between'}),
                        dbc.Collapse([
                            html.Hr(className="my-2"),
                            filter_node_form,
                            filter_edge_form,
                        ], id="filter-show-toggle", is_open=False),

                        # ---- color section ----
                        # create_row([
                            html.H6("Color"), # heading
                            html.Div([
                                dbc.Button("Hide/Show", id="color-show-toggle-button", outline=True, color="secondary", size="sm"), # legend
                                dbc.Button("Legends", id="color-legend-toggle", outline=True, color="secondary", size="sm"), # legend
                            ]),
                            # add the legends popup
                            dbc.Popover(
                                children=color_legends,
                                id="color-legend-popup", is_open=False, target="color-legend-toggle",
                            ),
                        # ], {**fetch_flex_row_style(), 'margin-left': 0, 'margin-right':0, 'justify-content': 'space-between'}),
                        dbc.Collapse([
                            html.Hr(className="my-2"),
                            get_select_form_layout(
                                id='color_nodes',
                                options=[{'label': opt, 'value': opt} for opt in cat_node_features],
                                label='Color nodes by',
                                description='Select the categorical node property to color nodes by'
                            ),
                            get_select_form_layout(
                                id='color_edges',
                                options=[{'label': opt, 'value': opt} for opt in cat_edge_features],
                                label='Color edges by',
                                description='Select the categorical edge property to color edges by'
                            ),
                        ], id="color-show-toggle", is_open=True),

                        # ---- size section ----
                        # create_row([
                            html.H6("Size"), # heading
                            dbc.Button("Hide/Show", id="size-show-toggle-button", outline=True, color="secondary", size="sm"), # legend
                        dbc.Collapse([
                            html.Hr(className="my-2"),
                            get_select_form_layout(
                                id='size_nodes',
                                options=[{'label': opt, 'value': opt} for opt in num_node_features],
                                label='Size nodes by',
                                description='Select the numerical node property to size nodes by'
                            ),
                            get_select_form_layout(
                                id='size_edges',
                                options=[{'label': opt, 'value': opt} for opt in num_edge_features],
                                label='Size edges by',
                                description='Select the numerical edge property to size edges by'
                            ),
                        ], id="size-show-toggle", is_open=True),
    ],
    
    style=SIDEBAR_STYLE,
    )
    
    page_for_case = html.Div(id="page_for_case", children=True, style={"margin-left":"300px", "margin-top": "30px"})
    page_for_sub = html.Div(id="page_for_sub", children=True, style={"margin-left":"300px", "margin-top": "30px"})
    page_for_catalog = html.Div(id="page_for_catalog", children=True, style={"margin-left":"300px", "margin-top": "30px"})
    map = html.Div(id="data-flow-map", children=[])
        
    return html.Div([
        map,
        page_for_sub,
        page_for_case,
        page_for_catalog,
        side_bar
    ])

def create_case_show(map_list):
    popovers = []
    for i in map_list:
        key = i
        value = map_list[i]
        popovers.append(
            dbc.Card(
                [
                    dbc.CardImg(src="/static/images/placeholder286x180.png", top=True),
                    dbc.CardBody(
                        [
                            html.H4(key, className="card-title"),
                            html.P(
                                value,
                                className="card-text",
                                id=key,
                                style={
                                    # "width": "11rem",
                                    # "height": "9rem",
                                    "text-overflow":"ellipsis",
                                    "overflow":"hidden",
                                    # "white-space":"pre-line"
                                    "display":"-webkit-box",

                                    "-webkit-line-clamp":"6",

                                    "-webkit-box-orient":"vertical"
                                }
                            ),
                        ],
                        style={
                            # "width": "15rem",
                            # "height": "15rem",
                            # "text-overflow":"ellipsis",
                            # "overflow":"hidden",
                            # "white-space":"overflow"
                        }, 
                    ),
                ],
                style={
                    "width": "18rem",
                    # "height": "18rem",
                    # "text-overflow":"ellipsis",
                    # "overflow":"hidden",
                    # "white-space":"overflow"
                }, 
            )
        )
        popovers.append(
            dbc.Popover(
                [
                    dbc.PopoverBody(value),
                ],
                target=key,
                trigger='hover'
            ),
        )        
    colitems = []
    for j in popovers:
        colitems.append(
            dbc.Col(j, width="auto")
        )
    result = dbc.Row(
        colitems
    )

    return result

def create_case_show2(map_list):
    popovers = []
    for index, j in enumerate(map_list):
        for i in j:
            key = i
            value = map_list[index][i]
            popovers.append(
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.H4(key, className="card-title"),
                                html.P(
                                    value,
                                    className="card-text",
                                    id=key,
                                    style={
                                        # "width": "11rem",
                                        # "height": "9rem",
                                        "text-overflow":"ellipsis",
                                        "overflow":"hidden",
                                        # "white-space":"pre-line"
                                        "display":"-webkit-box",

                                        "-webkit-line-clamp":"6",

                                        "-webkit-box-orient":"vertical"
                                    }
                                ),
                            ],
                            style={
                                # "width": "15rem",
                                # "height": "15rem",
                                # "text-overflow":"ellipsis",
                                # "overflow":"hidden",
                                # "white-space":"overflow"
                            }, 
                        ),
                    ],
                    style={
                        "width": "18rem",
                        # "height": "18rem",
                        # "text-overflow":"ellipsis",
                        # "overflow":"hidden",
                        # "white-space":"overflow"
                    }, 
                )
            )
            popovers.append(
                dbc.Popover(
                    [
                        dbc.PopoverBody(value),
                    ],
                    target=key,
                    trigger='hover'
                ),
            )        
    colitems = []
    for j in popovers:
        colitems.append(
            dbc.Col(j, width="auto")
        )
    result = dbc.Row(
        colitems
    )

    return result
