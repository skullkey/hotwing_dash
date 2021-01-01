import dash_editor_components
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc

import gcode_gen
import config_options
import plotting

cfg = config_options.Config("example.cfg")
with open("example.cfg") as f:
    lines = f.readlines()


# Build App
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP] )

["initial_move","profile","done_profile", "front_stock", "tail_stock"]
inline_checklist = dbc.FormGroup(
                [
                    dbc.Checklist(
                        options=[
                            {"label": "Initial Move", "value": "initial_move"},
                            {"label": "Profile", "value": "profile"},
                            {"label": "Post Profile", "value": "done_profile"},
                            {"label": "Front Stock", "value": "front_stock"},
                            {"label": "Tail Stock", "value": "tail_stock"},

                        ],
                        value=["profile"],
                        id="checklist-input",
                        inline=True,
                    ),
                ]
            )

app.layout = html.Div([
    dbc.Alert([html.H4("Hot Wing", className="alert-heading"),], color="dark"),
    
    html.Div(id='output-state'),
    dbc.Row([
        dbc.Col(
            dbc.Button(id='submit-button-state', n_clicks=0, children='Submit', color="primary", block=True),
        ),
        dbc.Col(
            dbc.Form([inline_checklist])
        )
    ]),
    dbc.Row(
            [
                dbc.Col(html.Div(
                        dash_editor_components.PythonEditor(
                            id='input', value = "".join(lines)
                        ), className="panel panel-body"
                    )
                ),
                dbc.Col(html.Div([dcc.Graph(id='graph_profile'),
                                  dcc.Graph(id='graph_plan'),
                                  dcc.Graph(id='graph'),

                        ])
                ),
            ]
        ),

])

@app.callback([Output('output-state', 'children'), Output("graph", "figure"),
              Output("graph_profile", "figure"), Output("graph_plan", "figure"),],
              [Input('submit-button-state', 'n_clicks'),Input("checklist-input", "value")], 
              State('input', 'value')
              
              )
def update_output(n_clicks, draw_selection, config_input):
    try:
        cfg.config.clear()
        cfg.config.read_string(config_input)
        old_kerf = cfg.get_config('Machine','Kerf')
        cfg.config.set('Machine','Kerf', "0")

        gc_gen = gcode_gen.GcodeGen(cfg)
        gc = gc_gen.gen_gcode()
        
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
        
        fig, stats = gplt.plot_gcode(pgc_filtered, draw_cutting_path=True,draw_foam_block=True, num_of_points=-1)


        camera = dict(
            eye=dict(x=-2.5, y=-2.5, z=2.5)
        )

        fig.update_layout(scene_camera=camera, legend=dict(
            orientation="h",)
        )
        
        
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
            autosize=False,
            height = 300,
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
        msg = {} #dbc.Alert("All Good", color="success")
    except Exception as e:
        msg = msg = dbc.Alert(str(e), color="danger")
        fig = {}
        fig_p = {}
        fig_plan = {}
    
    return msg, fig, fig_p, fig_plan


if __name__ == '__main__':
    app.run_server(debug=True, port=8889)