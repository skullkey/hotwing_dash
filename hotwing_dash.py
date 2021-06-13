#import dash_editor_components
import dash
import dash_ace
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash_extensions import Download
from dash_extensions import Keyboard

import gcode_gen
import config_options
import plotting

import flask
from flask import jsonify
from flask_cors import CORS
from flask import request

server = flask.Flask(__name__)
CORS(server)

from werkzeug.utils import secure_filename
import os
UPLOAD_FOLDER = "/tmp"

import unicodedata
import string
import base64

import json
import glob
import traceback

from utils import *
from dash.exceptions import PreventUpdate

import ezdxf
import dxf_parser
import plotly.graph_objects as go
import utils


cfg = config_options.Config()

with open("example.cfg") as f:
    config_template = f.read()

profile_cache = gcode_gen.ProfileCache("profiles")

# Build App
app = dash.Dash(__name__,
                server=server,
                routes_pathname_prefix='/',
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True,
                prevent_initial_callbacks=True,
                assets_folder='static', 
                title="Hotwing-Dash"
                )


default_check_list = ["profile"] 
inline_checklist = dbc.FormGroup(
                [
                    dbc.Checklist(
                        options=[
                            {"label": "Initial Move", "value": "initial_move"},
                            {"label": "Profile", "value": "profile"},
                            {"label": "Pre-Stock", "value": "done_profile"},
                            {"label": "Front Stock", "value": "front_stock"},
                            {"label": "Tail Stock", "value": "tail_stock"},
                       
                            #{"label": "Final", "value": "final"},
                            {"label": "With Kerf", "value": "kerf"},
                            {"label": "3D", "value": "3d"},
                            {"label": "Full Screen", "value": "full_screen"},


                        ],
                        value=default_check_list,
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
    ]),

  
], id='file_open_div')



gen_layout =  html.Div([
    
    html.Div(id='output-state'),
    dbc.Button(id='close-button-state', n_clicks=0, children='Close', color="danger", className="mr-2"),                   
    dbc.Button(id='save-button-state', n_clicks=0, children='Download', color="success", className="mr-2"),
    dbc.Button(id='submit-button-state', n_clicks=0, children='Draw (Ctrl+Enter)', color="primary", className="mr-2"),
    Download(id="download"),
    dcc.ConfirmDialog(
        id='confirm',
        message='Are you sure you want to close the config file?',
    ),

    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    Keyboard(id="keyboard"), html.Div(id="output"),
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
                        maxLines=60,
                        style={"width":"100%"}
                    )
                ])
            ), className="col-6", id='editor-card',
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
        ], className="col-6",id="chart-card"),
    ]),
    Download(id="download-gcode"),
    dcc.Textarea(id="gcode", value="",style={'display':'none'}),
], id="gen_div", style={"display":"none"})

main_tab_layout.children = [file_open_layout, gen_layout]

with open("README.md") as f:
    info_md = f.read()

info_tab_layout = html.Div([
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Markdown(info_md, dangerously_allow_html=True)
                ])
            )
        )
    ])
])


with open("gallery.md") as f:
    gallery_md = f.read()

gallery_tab_layout = html.Div([
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Markdown(gallery_md, dangerously_allow_html=True)
                ])
            )
        )
    ])
])



dxf2gcode_tab_layout = html.Div([

    dbc.Row([
        dbc.Col([
            dcc.Upload(id='d2g-upload-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select DXF (Only Line and LWPolyLine Elements supported) or previously generated GCode Files')
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


    ]),
    html.Div([

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Profile From DXF",id="g2g-profile-header"),
                    dbc.CardBody(
                        html.Div([dcc.Graph(id='d2g_graph_profile', config={'displayModeBar': False}),
                            ])
                    )
                ]),
            ], className="col-12",id="d2g-chart-card"),
        ]),

        dbc.Row([
            dbc.Col([
                dbc.Row([
                    dbc.Col([
                        'Filename',
                        dbc.Input(id="uploaded-filename", className="mr-2",type='text',disabled = True, value=''),
                    ], className='col-3'),
                    dbc.Col([
                        'X-Offset',
                        dbc.Input(id="d2g-x-offset", className="mr-2", type='number', value=0),
                    ], className='col-3'),
                    dbc.Col([
                        'Y-Offset',
                        dbc.Input(id="d2g-y-offset", className="mr-2", type='number', value=0),

                    ], className='col-3'),
                    dbc.Col([
                        html.Br(),
                        dbc.Button(id='d2g-submit-button', n_clicks=0, children='Update', color="primary", className="mr-2"),
                    ], className='col-3'),

                ]),
                dbc.Row([
                    dbc.Col([
                        'Four Axes',
                        dcc.Dropdown(id='d2g-four-axes',
                            options=[
                                {'label': '2', 'value': '2'},
                                {'label': '4      ', 'value': '4'},
                            ],
                            value='4',
                        ) , 
                    ], className='col-3'),
                    dbc.Col([
                        'Feedrate',
                        dbc.Input(id="d2g-feedrate", className="mr-2", type='number', value=160),
                    ], className='col-3'),
                    dbc.Col([
                        'PWM',
                        dbc.Input(id="d2g-pwm", className="mr-2", type='number', value=60),
                    ], className='col-3'),

                    dbc.Col([
                        html.Br(),
                        dbc.Button(id='d2g-download-button', n_clicks=0, children='Download', color="success", className="mr-2"),
                        dbc.Button(id='d2g-selig-button', n_clicks=0, children='Selig', color="success", className="mr-2"),

                    ], className='col-3'),

                ]),

                
                #"Starting Position",
                #dbc.Input(id="d2g-starting", className="mr-2",     placeholder='Select a starting point for the cut...',  type='text',  value='', disabled=True),
                



                
                dbc.Input(id="d2g-filename", type='hidden', value=''),

                dcc.Download(id="download-d2g-gcode"),
                dcc.Download(id="download-d2g-selig")


            ], className='col-9')
        ]),
    ], style={"display":"none"}, id='d2g-profile-view')
], id="d2g_gen_div")

@app.callback([Output("d2g_graph_profile", "figure"), Output("d2g-filename","value"), 
                Output('uploaded-filename','value'), Output('d2g-profile-view','style'),
                Output('d2g-x-offset','value'), Output('d2g-y-offset','value')], 
              [Input('d2g-upload-data',"contents"), Input('d2g-submit-button','n_clicks'), Input('d2g-x-offset','value'), Input('d2g-y-offset','value'),  ],
              [ State('d2g-filename','value'), State('d2g-upload-data', 'filename'),])
def draw_dxf(contents, n, x_offset, y_offset, stored_filename, uploaded_filename):

    ctx = dash.callback_context




    if not ctx.triggered:
        button_id = None
        return "","","",{'display:none'},x_offset, y_offset
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == "d2g-upload-data":
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            stored_filename = utils.get_temp_filename(UPLOAD_FOLDER)
            _,extension =  os.path.splitext(uploaded_filename)
            extension = extension.lower()

            stored_filename = os.path.join(UPLOAD_FOLDER, secure_filename(stored_filename)) + extension
            with open(stored_filename, "wb") as f:
                f.write(decoded)

        dxfp = dxf_parser.create_parser(stored_filename)

        x_series, y_series, x_offset, y_offset = dxfp.to_xy_array(x_offset, y_offset, ignore_offset= button_id == "d2g-upload-data")

        fig = go.Figure()

        fig.add_trace(go.Scatter(x=x_series, y=y_series,
                            mode='lines+markers',
                            name='lines+markers'))
        fig.update_layout(scene_aspectmode='data')
        fig.update_yaxes(
                    scaleanchor = "x",
                    scaleratio = 1,
                    constrain='domain'
                )

        fig.update_layout(clickmode='event+select')



        return fig, stored_filename, uploaded_filename, {'display':''}, x_offset, y_offset


@app.callback(Output('download-d2g-gcode','data'), Input('d2g-download-button','n_clicks'), 
                [State('uploaded-filename','value'), State('d2g-filename','value'), 
                State('d2g-x-offset','value'), State('d2g-y-offset','value'),
                State('d2g-four-axes','value'), State('d2g-feedrate','value'), State('d2g-pwm','value')

                ], prevent_initial_call=True)
def download_d2g_gcode(n_clicks, uploaded_filename, stored_filename, x_offset, y_offset, four_axis, feedrate, pwm):

    dxfp = dxf_parser.create_parser(stored_filename)
    gcode = dxfp.to_gcode(x_offset, y_offset, four_axis=='4', feedrate, pwm)

    _,extension =  os.path.splitext(stored_filename)
    extension = extension.lower()
    if extension != '.gcode':
        downloadfilename = uploaded_filename + '.gcode'
    else:
        downloadfilename = uploaded_filename

    return dict(content="\n".join(gcode), filename=downloadfilename)


@app.callback(Output('download-d2g-selig','data'), Input('d2g-selig-button','n_clicks'),
        [State('uploaded-filename','value'), State('d2g-filename','value'), 
                State('d2g-x-offset','value'), State('d2g-y-offset','value'),
                State('d2g-four-axes','value'), State('d2g-feedrate','value'), State('d2g-pwm','value')
        ])
def download_selig(selig_clicks,  uploaded_filename, stored_filename, x_offset, y_offset, four_axis, feedrate, pwm):
    dxfp = dxf_parser.create_parser(stored_filename)  
    output = dxfp.to_selig(uploaded_filename)
    
    return dict(content="\n".join(output), filename = uploaded_filename+".dat")  



app.layout = dbc.Tabs([
    dbc.Tab(info_tab_layout, label="Info"),
    dbc.Tab(main_tab_layout, label="Wing Gcode"),
    dbc.Tab(dxf2gcode_tab_layout, label="Dxf to Gcode"),
    dbc.Tab(gallery_tab_layout, label="Gallery"),
], id="tabs")





@app.callback(Output("download-gcode", "data"), 
              [Input("save-button-state", "n_clicks")], 
              State('gcode', 'value'))
def save_config(n_nlicks, gcode_input):

    pn = cfg.get_config("Project","Name")
    filename = "%s.gcode" % removeDisallowedFilenameChars(pn)

    
    return dict(content=gcode_input, filename=filename)




@app.callback([Output("file_open_div","style"), 
                Output("gen_div","style"), 
                Output('input', 'value'),
                Output("checklist-input", "value") ], 
                [Input("new-config","n_clicks"), 
                Input("confirm","submit_n_clicks"),
                Input('upload-data',"contents")])
def update_main_content(n_clicks_new, n_clicks_close, contents):
    ctx = dash.callback_context

    hide = {'display':'none'}
    show = {'display':''}
    
    if not ctx.triggered:
        button_id = None
        return show,hide,"", default_check_list
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == "new-config":
            return hide, show, config_template, default_check_list
        elif button_id == "close-button-state":
            return show, hide, "", default_check_list
        elif button_id == "upload-data":
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string).decode()
            prepped = parse_uploaded(decoded)
            return  hide, show, prepped, default_check_list

    return show, hide, "", default_check_list


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
               Input("point-slider","value"),
               Input("keyboard", "keydown")], 
              State('input', 'value')
              
              )
def update_output(n_clicks, draw_selection, point_slider, keyboard_event, config_input):
    ctx = dash.callback_context
    input_trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    if input_trigger == 'keyboard':
        if keyboard_event.get('key',"") == "Enter" and keyboard_event.get('ctrlKey',False) :
            pass
        else:
            raise PreventUpdate

    EDITOR_SHOW = {'display':''}
    EDITOR_HIDE = {'display':'none'}
    validation = []

    output_error_msg = {} 
    try:
        validation = cfg.read_string(config_input)
        if validation:
            if config_input == "":
                err_msg = ""
            else:
                err_msg = list_to_html(validation)
            output_error_msg = dbc.Alert(err_msg, color="danger")
            raise Exception("Validation Failed")
            
        # remove the kerf by setting to zero to visualize the profiles
        if "kerf" not in draw_selection:
            old_kerf = cfg.get_config('Machine','Kerf')
            cfg.config.set('Machine','Kerf', "0")

        gc_gen = gcode_gen.GcodeGen(cfg, profile_cache)
        gc, bbox, wing_plan = gc_gen.gen_gcode()
        gcode_output = gc.code_as_str
        
        pgc = plotting.ParsedGcode.fromgcode(gc)

        machine_width = cfg.get_config('Machine',"Width")
        machine_height=cfg.get_config('Machine',"Height")
        machine_depth=cfg.get_config('Machine',"Depth")

        panel_offset = gc_gen.left_offset
        panel_width = bbox[1,0] - bbox[0,0]

        panel_bottom = cfg.get_config('Panel','Bottom')
        panel_height = cfg.get_config('Panel','Height')
        panel_inset = cfg.get_config('Panel','Inset')
        panel_depth = cfg.get_config('Panel','Depth')

        gplt = plotting.GcodePlotter(machine_width,machine_height, machine_depth,
                                    panel_offset, panel_width,
                                    panel_bottom, panel_height, 
                                    panel_inset, panel_depth, wing_plan, bbox)
        pgc_filtered = pgc.filter_gcode(draw_selection)


        fig, stats_3d = gplt.plot_gcode(pgc_filtered, draw_cutting_path=True,draw_foam_block=True, num_of_points=-1)
        wing_stats = gc_gen.calc_wing_stats()
        stats_3d['wing_stats'] = wing_stats

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

        # put old kerf back to make sure gcode in output box contains the right kerf setting
        if "kerf" not in draw_selection:
            cfg.config.set('Machine','Kerf', old_kerf)
            gc_gen = gcode_gen.GcodeGen(cfg, profile_cache)
            gc, _, _ = gc_gen.gen_gcode()
            gcode_output = gc.code_as_str
  
    except Exception as e:
        traceback.print_exc()
        if not validation:
            output_error_msg = dbc.Alert(str(e), color="danger")
        fig = {}
        fig_p = {}
        fig_plan = {}
        gcode_output = "Error: %s" % str(e)
        editor_visible = EDITOR_SHOW
        stats_output = ""
    
    return output_error_msg, fig, fig_p, fig_plan, gcode_output, editor_visible, stats_output

@app.callback(Output("chart-card","className"),
               Input("editor-card","style"))
def update_card_classnames(style):
    if style['display'] == 'none':
        return "col-12"
    else:
        return "col-6"

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
    if children == "":
        return {},{},""
    else:
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


        output.append('Wing Area (cm2): %.2f' % (stats['wing_stats']['wing_area'] / 100 ) )
        output.append('Wing Area (sq.in): %.2f' % (stats['wing_stats']['wing_area'] / 100 / 6.4516 ) )
        output.append('Wing Area (sq.ft): %.2f' % (stats['wing_stats']['wing_area'] / 100 * 0.00107639 ) )
        output.append('Wing Loading @ 100g (oz/sq.ft): %.2f' % (100.  / (stats['wing_stats']['wing_area']/ 100. * 0.00107639) / 28.35  ) )
        output.append('Wing Cube Loading @ 100g (oz/sq.ft): %.2f' % (100.  / (stats['wing_stats']['wing_area']/ 100. * 0.00107639) **1.5 / 28.35  ) )

        

        
        output.append('Aspect Ratio: %.2f' % (stats['wing_stats']['aspect_ratio']  ) )
        output.append('Taper Ratio: %.2f'  % (stats['wing_stats']['taper_ratio']))
        output.append('MAC (mm): %.2f'  % (stats['wing_stats']['mac']))
        #output.append('MAC_X: %.2f'  % (stats['wing_stats']['mac_x']  ))
        output.append('MAC Distance (mm): %.2f'  % (stats['wing_stats']['mac_y']  ))

        output.append('CG (15%%) (mm): %.2f'  % (stats['wing_stats']['mac_x'] + stats['wing_stats']['mac'] * 0.15 ))
        output.append('CG (20%%) (mm): %.2f'  % (stats['wing_stats']['mac_x'] + stats['wing_stats']['mac'] * 0.2 ))
        output.append('CG (25%%) (mm): %.2f'  % (stats['wing_stats']['mac_x'] + stats['wing_stats']['mac'] * 0.25 ))



        output_html = html.Div([html.Ul([html.Li(w) for w in output])])

        return profile_header,\
            plan_header, \
            output_html






@server.route('/autocompleter', methods=['GET'])
def autocompleter():
    prefix = request.args.get("prefix")
    autocomplete = []

    if profile_cache.path in prefix:
        profile_names = glob.glob(profile_cache.path + "/*.dat")
        for p in profile_names:
            p = p.split("/")[-1]
            autocomplete.append({"name": p, "value": p, "score": 1000, "meta": "Profile"})

    elif '=' in prefix:
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