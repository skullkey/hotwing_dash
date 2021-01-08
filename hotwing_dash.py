#import dash_editor_components
import dash
import dash_ace
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash_extensions import Download

import gcode_gen
import config_options
import plotting

import flask
from flask import jsonify
from flask_cors import CORS
from flask import request

server = flask.Flask(__name__)
CORS(server)


import unicodedata
import string
import base64

import json

validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)

def removeDisallowedFilenameChars(filename):
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)


cfg = config_options.Config("")

with open("example.cfg") as f:
    config_template = f.read()

# Build App
app = dash.Dash(__name__,
                server=server,
                routes_pathname_prefix='/hw/',
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True,
                prevent_initial_callbacks=True,
                assets_folder='static'
                )

inline_checklist = dbc.FormGroup(
                [
                    dbc.Checklist(
                        options=[
                            {"label": "Initial Move", "value": "initial_move"},
                            {"label": "Profile", "value": "profile"},
                            {"label": "Pre-Stock", "value": "done_profile"},
                            {"label": "Front Stock", "value": "front_stock"},
                            {"label": "Tail Stock", "value": "tail_stock"},
                            {"label": "With Kerf", "value": "kerf"},
                            {"label": "3D", "value": "3d"},
                            {"label": "Full Screen", "value": "full_screen"},


                        ],
                        value=["profile"],
                        id="checklist-input",
                        inline=True,
                    ),
                ]
            )



main_tab_layout = html.Div(id = "main-content")

file_open_layout = html.Div([
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.Center(dbc.Button("New", id="new-config", className="col-2", style={'horizontalAlign':'center'})),
                    html.Br(),
                    dcc.Upload(id='upload-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select Files')
                        ]),
                        style={
                            'width': '100%',
                            'height': '60px',
                            'lineHeight': '60px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'margin': '10px'
                        },)
                ])
            )
        )
    ])
], id='file_open_div')



gen_layout =  html.Div([
    
    html.Div(id='output-state'),
    dbc.Button(id='close-button-state', n_clicks=0, children='Close', color="danger", className="mr-2"),                   
    dbc.Button(id='save-button-state', n_clicks=0, children='Download', color="success", className="mr-2"),
    dbc.Button(id='submit-button-state', n_clicks=0, children='Draw', color="primary", className="mr-2"),
    Download(id="download"),
    dcc.ConfirmDialog(
        id='confirm',
        message='Are you sure you want to close the config file?',
    ),

    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([


                    #dash_editor_components.PythonEditor(
                    #    id='input', value = "".join(lines)
                    #),
                    dash_ace.DashAceEditor(
                        id='input',
                        value="",
                        theme='tomorrow',
                        mode='norm',
                        tabSize=2,
                        enableBasicAutocompletion=True,
                        enableLiveAutocompletion=False,
                        syntaxFolds = "\\[)(.*?)(",
                        autocompleter='/autocompleter?prefix=',
                        placeholder='Python code ...',
                        wrapEnabled=True,
                        prefixLine=True,
                        style={"width":"100%"}
                    )
                ])
            ), className="col-5", id='editor-card',
        ),
        dbc.Col([
            dbc.Form([inline_checklist]),
            dbc.Card([
                dbc.CardHeader("Profile",id="profile-header"),
                dbc.CardBody(
                    html.Div([dcc.Graph(id='graph_profile', config={'displayModeBar': False}),
                        ])
                )
            ]),
            dbc.Card([
                dbc.CardHeader("Plan", id="plan-header"),
                dbc.CardBody(
                    html.Div([
                                dcc.Graph(id='graph_plan', config={'displayModeBar': False}),
                        ])
                )
            ]),
            dbc.Card([
                dbc.CardHeader("Visualization"),
                dbc.CardBody(
                    html.Div([
                                dcc.Graph(id='graph', config={'displayModeBar': False}),
                                dcc.Slider(
                                    id='point-slider',
                                    min=1,
                                    max=100,
                                    step=1,
                                    value=100,
                                ),
                        ])
                )
            ], id='3d-card',  style={"display":"none"} ),
            dbc.Card([
                dbc.CardHeader("Stats"),
                dbc.CardBody([
                    html.Div( id="stats-div", style={"display":"none"}),
                    html.Div(id="stats-output-div")
                ])
            ])
        ], className="col-7",id="chart-card"),
    ]),

], id="gen_div", style={"display":"none"})

main_tab_layout.children = [file_open_layout, gen_layout]

with open("info.md") as f:
    info_md = f.read()

info_tab_layout = html.Div([
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Markdown(info_md)
                ])
            )
        )
    ])
])

gcode_tab_layout = html.Div([
    dbc.Button(id='save-gcode-button', n_clicks=0, children='Download', color="success", className="mr-2"),
    Download(id="download-gcode"),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([


                    dash_ace.DashAceEditor(
                        id='gcode',
                        value="",
                        theme='github',
                        mode='text',
                        tabSize=2,
                        enableBasicAutocompletion=False,
                        enableLiveAutocompletion=False,
                        placeholder='No gcode ...',
                        wrapEnabled=True,
                        style={"width":"100%"}
                    )
                ])
            )
        )
    ])

])



app.layout = dbc.Tabs([
    dbc.Tab(info_tab_layout, label="Info"),
    dbc.Tab(main_tab_layout, label="Generate"),
    dbc.Tab(gcode_tab_layout, label="GCode"),

])


@app.callback(Output("download", "data"), [Input("save-button-state", "n_clicks")], State('input', 'value'))
def save_config(n_nlicks, config_input):
    cfg.config.clear()
    cfg.config.read_string(config_input)
    pn = cfg.get_config("Project","Name")
    filename = removeDisallowedFilenameChars(pn)

    
    return dict(content=config_input, filename=filename)


@app.callback(Output("download-gcode", "data"), 
              [Input("save-gcode-button", "n_clicks")], 
              State('gcode', 'value'))
def save_config(n_nlicks, gcode_input):

    pn = cfg.get_config("Project","Name")
    filename = "%s.gcode" % removeDisallowedFilenameChars(pn)

    
    return dict(content=gcode_input, filename=filename)




@app.callback([Output("file_open_div","style"), 
                Output("gen_div","style"), 
                Output('input', 'value')], 
                [Input("new-config","n_clicks"), 
                Input("confirm","submit_n_clicks"),
                Input('upload-data',"contents")])
def update_main_content(n_clicks_new, n_clicks_close, contents):
    ctx = dash.callback_context

    hide = {'display':'none'}
    show = {'display':''}
    
    if not ctx.triggered:
        button_id = None
        return show,hide,""
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == "new-config":
            return hide, show, config_template
        elif button_id == "close-button-state":
            return show, hide, ""
        elif button_id == "upload-data":
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string).decode()
            return  hide, show, decoded

    return show, hide, ""


@app.callback(Output('confirm', 'displayed'),
              Input('close-button-state', 'n_clicks'))
def display_confirm(value):
    return True



@app.callback([Output('output-state', 'children'), 
                Output("graph", "figure"),
                Output("graph_profile", "figure"), 
                Output("graph_plan", "figure"), 
                Output('gcode','value'), 
                Output('editor-card', 'style'),
                Output('stats-div','children')
                ],
              [Input('submit-button-state', 'n_clicks'), 
               Input("checklist-input", "value"),
               Input("point-slider","value")], 
              State('input', 'value')
              
              )
def update_output(n_clicks, draw_selection, point_slider, config_input):
    #return {}, {}, {}, {}, {}
    EDITOR_SHOW = {'display':''}
    EDITOR_HIDE = {'display':'none'}
    try:
        cfg.config.clear()
        cfg.config.read_string(config_input)
        if "kerf" not in draw_selection:
            old_kerf = cfg.get_config('Machine','Kerf')
            cfg.config.set('Machine','Kerf', "0")

        gc_gen = gcode_gen.GcodeGen(cfg)
        gc = gc_gen.gen_gcode()
        gcode_output = gc.code_as_str
        
        pgc = plotting.ParsedGcode.fromgcode(gc)

        machine_width = cfg.get_config('Machine',"Width")
        machine_height=cfg.get_config('Machine',"Height")
        machine_depth=cfg.get_config('Machine',"Depth")

        panel_offset = gc_gen.left_offset
        panel_width = cfg.get_config('Panel',"Width")
        panel_bottom = cfg.get_config('Panel','Bottom')
        panel_height = cfg.get_config('Panel','Height')
        panel_inset = cfg.get_config('Panel','Inset')
        panel_depth = cfg.get_config('Panel','Depth')

        gplt = plotting.GcodePlotter(machine_width,machine_height, machine_depth,
                                    panel_offset, panel_width,
                                    panel_bottom, panel_height, 
                                    panel_inset, panel_depth)
        pgc_filtered = pgc.filter_gcode(draw_selection)


        fig, stats_3d = gplt.plot_gcode(pgc_filtered, draw_cutting_path=True,draw_foam_block=True, num_of_points=-1)
        stats_output = json.dumps(stats_3d)
        if "3d" in draw_selection:

            point_perc = float(point_slider) / 100.0
            num_of_points = int(point_perc * len(pgc_filtered))

            if point_perc != 1:
                fig, _ = gplt.plot_gcode(pgc_filtered, draw_cutting_path=True,draw_foam_block=True, num_of_points=num_of_points)


            camera = dict(
                eye=dict(x=-2.5, y=-2.5, z=2.5)
            )

            fig.update_layout( 
                legend=dict(orientation="h"),
                uirevision= "ssss"
            )
        else:
            fig = {}

        if "full_screen" in draw_selection:
            editor_visible = EDITOR_HIDE
        else:
            editor_visible = EDITOR_SHOW
        
        
        fig_p, stats = gplt.plot_gcode_2dprofile(pgc_filtered, draw_cutting_path=True,
                                       draw_foam_block=True, draw_machine_block = False,
                                       num_of_points=-1)
        fig_p.update_yaxes(
            scaleanchor = "x",
            scaleratio = 1,
            constrain='domain'
        )

        fig_p.update_xaxes(range=[panel_inset-50, panel_inset + panel_depth+50], constrain="domain")

        fig_p.update_layout(
            autosize=False,
            height = 200,
            plot_bgcolor="#FFF",
            xaxis=dict(
                linecolor="#BCCCDC",  # Sets color of X-axis line
                showgrid=False  # Removes X-axis grid lines
            ),
            yaxis=dict(
                linecolor="#BCCCDC",  # Sets color of Y-axis line
                showgrid=False,  # Removes Y-axis grid lines    
            )
        )

        
        fig_p.update_layout(legend=dict(
            orientation="h"
        ))
        
        fig_plan, stats = gplt.plot_gcode_2dplan(pgc_filtered, draw_cutting_path=True,draw_foam_block=True, 
                                    draw_machine_block = True, num_of_points=-1)
        fig_plan.update_yaxes(
            scaleanchor = "x",
            scaleratio = 1,
        )

        fig_plan.update_yaxes(
            range=(-50, machine_depth+50),
            constrain='domain'
        )

        fig_plan.update_layout(
            autosize=True,
            #height = 300,
            plot_bgcolor="#FFF",
            xaxis=dict(
                linecolor="#BCCCDC",  # Sets color of X-axis line
                showgrid=False  # Removes X-axis grid lines
            ),
            yaxis=dict(
                linecolor="#BCCCDC",  # Sets color of Y-axis line
                showgrid=False,  # Removes Y-axis grid lines    
            )
            
        )

        fig_plan.update_layout(legend=dict(
            orientation="h"
        ))
        msg = {} 
    except Exception as e:
        msg = dbc.Alert(str(e), color="danger")
        fig = {}
        fig_p = {}
        fig_plan = {}
        gcode_output = "Error: %s" % str(e)
        editor_visible = EDITOR_SHOW
        stats_output = ""
    
    return msg, fig, fig_p, fig_plan, gcode_output, editor_visible, stats_output

@app.callback(Output("chart-card","className"),
               Input("editor-card","style"))
def update_card_classnames(style):
    if style['display'] == 'none':
        return "col-12"
    else:
        return "col-7"

@app.callback( Output("3d-card", "style"), Input("graph", "figure"))
def show_or_hide_3d(fig):
    if fig == {}:
        return {"display":"none"}
    else:
        return {"display":"block"}


@app.callback([Output("profile-header","style"), 
                Output("plan-header","style"),
                Output("stats-output-div","children")],
              Input("stats-div","children"))
def show_card_head_warning(children):
    stats = json.loads(children)
    output = []
    
    output.append('Wing Out of Bounds: %d ' % stats['wing']['out_of_bounds'])
    if stats['wing']['out_of_bounds'] > 0:
        profile_header = {"background-color":"#dc3545","color":"white"}
    else:
        profile_header = {}

    if stats['machine']['out_of_bounds'] > 0:
        plan_header = {"background-color":"#dc3545","color":"white"}
    else:
        plan_header = {}        

    return profile_header,\
           plan_header, \
           output

@server.route('/autocompleter', methods=['GET'])
def autocompleter():
    prefix = request.args.get("prefix")
    print(prefix)
    autocomplete = []

    if '=' in prefix:
        parameter = prefix.split("=")[0].strip()
        parameter_lookup = prefix.split("=")[-1]
        for heading, section in cfg.CONFIG_OPTIONS.items():
            param_confg = section.get(parameter, {}) 
            domain = param_confg.get("domain",[])
            for d in domain:
                autocomplete.append({"name": d, "value": d, "score": 1000, "meta": "Parameter"})

    else:
        for heading, section in cfg.CONFIG_OPTIONS.items():
            for keyword, meta in section.items():
                if keyword.lower().startswith(prefix.lower()):
                    autocomplete.append({"name": keyword, "value": keyword, "score": 100, "meta": "Config"})
    return jsonify(autocomplete)



if __name__ == '__main__':
    app.run_server(debug=True, port=8050, host="0.0.0.0")