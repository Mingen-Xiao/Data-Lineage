# import
import io
import sys
import base64
import datetime
import dash
from dash import dash_table
from dash.dependencies import Input, Output, State
import dash_html_components as html
import dash_bootstrap_components as dbc
import visdcc
import pandas as pd
from .datasets.parse_dataframe import parse_dataframe
from .layout import create_case_show2, get_options, get_app_layout, get_distinct_colors, create_color_legend, DEFAULT_COLOR, \
    DEFAULT_NODE_SIZE, DEFAULT_EDGE_SIZE, create_case_show, get_select_form_layout
from .lineage import parse_subquery_and_case, parse_subquery_and_case2

# class
class Jaal:
    """The main visualization class
    """
    def __init__(self, edge_df, node_df=None):
        """
        Parameters
        -------------
        edge_df: pandas dataframe
            The network edge data stored in format of pandas dataframe

        node_df: pandas dataframe (optional)
            The network node data stored in format of pandas dataframe
        """
        print("Parsing the data...", end="")
        self.data, self.scaling_vars = parse_dataframe(edge_df, node_df)
        self.filtered_data = self.data.copy()
        self.node_value_color_mapping = {}
        self.edge_value_color_mapping = {}
        print("Done")

    def parse_contents(self, contents, filename, date):
        content_type, content_string = contents.split(',')

        decoded = base64.b64decode(content_string)

        if 'node' in filename:
            nodenedge_df = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        elif 'edge' in filename:
            nodenedge_df = pd.read_csv(
                io.StringIO(decoded.decode('utf-8')))
        return nodenedge_df

    def parse_sql_contents(self, contents, filename, date):
        content_type, content_string = contents.split(',')

        decoded = base64.b64decode(content_string)

        sql_df = pd.read_csv(
            io.StringIO(decoded.decode('utf-8')))
        return sql_df

    def parse_catalog_contents(self, contents, filename, date):
        content_type, content_string = contents.split(',')

        decoded = base64.b64decode(content_string)
        try:
            if 'csv' in filename:
                # Assume that the user uploaded a CSV file
                df = pd.read_csv(
                    io.StringIO(decoded.decode('utf-8')))
            elif 'xls' in filename:
                # Assume that the user uploaded an excel file
                df = pd.read_excel(io.BytesIO(decoded))
        except Exception as e:
            print(e)
            return html.Div([
                'There was an error processing this file.'
            ])

        return html.Div([
            html.H5(filename),
            html.H6(datetime.datetime.fromtimestamp(date)),

            dash_table.DataTable(
                df.to_dict('records'),
                [{'name': i, 'id': i} for i in df.columns],
                filter_action="native",
                sort_action="native",
            ),

            html.Hr(),  # horizontal line

            # For debugging, display the raw contents provided by the web browser
            html.Div('Raw Content'),
            html.Pre(contents[0:200] + '...', style={
                'whiteSpace': 'pre-wrap',
                'wordBreak': 'break-all'
            })
        ])

    def _callback_search_graph(self, graph_data, search_text):
        """Only show the nodes which match the search text
        """
        nodes = graph_data['nodes']
        edges = graph_data['edges']
        nodetest = []
        nodetest1 = []
        for node in nodes:
            # cancel the search
            if search_text == "":
                for edge in edges:
                    node['hidden'] = False
                    edge['hidden'] = False
            # do the search
            else:
                if search_text != node['label'].lower():
                    node['hidden'] = True
                    for edge in edges:
                        splitededge = edge['id'].split("__")
                        if((search_text == splitededge[0]) | (search_text == splitededge[1])) & ((node['label'] == splitededge[0]) | (node['label'] == splitededge[1])):
                            node['hidden'] = False
                        if((node['label'] == splitededge[0]) | (node['label'] == splitededge[1])):
                            edge['hidden'] = True
                            if((search_text == splitededge[0]) | (search_text == splitededge[1])):
                                edge['hidden'] = False
                else:
                    node['hidden'] = False
        graph_data['nodes'] = nodes
        return graph_data

    def _callback_filter_nodes(self, graph_data, filter_nodes_text):
        """Filter the nodes based on the Python query syntax
        """
        self.filtered_data = self.data.copy()
        node_df = pd.DataFrame(self.filtered_data['nodes'])
        try:
            node_list = node_df.query(filter_nodes_text)['id'].tolist()
            nodes = []
            for node in self.filtered_data['nodes']:
                if node['id'] in node_list:
                    nodes.append(node)
            self.filtered_data['nodes'] = nodes
            graph_data = self.filtered_data
        except:
            graph_data = self.data
            print("wrong node filter query!!")
        return graph_data

    def _callback_filter_edges(self, graph_data, filter_edges_text):
        """Filter the edges based on the Python query syntax
        """
        self.filtered_data = self.data.copy()
        edges_df = pd.DataFrame(self.filtered_data['edges'])
        try:
            edges_list = edges_df.query(filter_edges_text)['id'].tolist()
            edges = []
            for edge in self.filtered_data['edges']:
                if edge['id'] in edges_list:
                    edges.append(edge)
            self.filtered_data['edges'] = edges
            graph_data = self.filtered_data
        except:
            graph_data = self.data
            print("wrong edge filter query!!")
        return graph_data

    def _callback_color_nodes(self, graph_data, color_nodes_value):
        value_color_mapping = {}
        # color option is None, revert back all changes
        if color_nodes_value == 'None':
            # revert to default color
            for node in self.data['nodes']:
                node['color'] = DEFAULT_COLOR
        else:
            print("inside color node", color_nodes_value)
            unique_values = pd.DataFrame(self.data['nodes'])[color_nodes_value].unique()
            colors = get_distinct_colors(len(unique_values))
            value_color_mapping = {x:y for x, y in zip(unique_values, colors)}
            for node in self.data['nodes']:
                node['color'] = value_color_mapping[node[color_nodes_value]]
        # filter the data currently shown
        filtered_nodes = [x['id'] for x in self.filtered_data['nodes']]
        self.filtered_data['nodes'] = [x for x in self.data['nodes'] if x['id'] in filtered_nodes]
        graph_data = self.filtered_data
        return graph_data, value_color_mapping

    def _callback_size_nodes(self, graph_data, size_nodes_value):
        # color option is None, revert back all changes
        if size_nodes_value == 'None':
            # revert to default color
            for node in self.data['nodes']:
                node['size'] = DEFAULT_NODE_SIZE
        else:
            print("Modifying node size using ", size_nodes_value)
            # fetch the scaling value
            minn = self.scaling_vars['node'][size_nodes_value]['min']
            maxx = self.scaling_vars['node'][size_nodes_value]['max']
            # define the scaling function
            scale_val = lambda x: 20*(x-minn)/(maxx-minn)
            # set size after scaling
            for node in self.data['nodes']:
                node['size'] = node['size'] + scale_val(node[size_nodes_value])
        # filter the data currently shown
        filtered_nodes = [x['id'] for x in self.filtered_data['nodes']]
        self.filtered_data['nodes'] = [x for x in self.data['nodes'] if x['id'] in filtered_nodes]
        graph_data = self.filtered_data
        return graph_data

    def _callback_color_edges(self, graph_data, color_edges_value):
        value_color_mapping = {}
        # color option is None, revert back all changes
        if color_edges_value == 'None':
            # revert to default color
            for edge in self.data['edges']:
                edge['color']['color'] = DEFAULT_COLOR
        else:
            print("inside color edge", color_edges_value)
            unique_values = pd.DataFrame(self.data['edges'])[color_edges_value].unique()
            colors = get_distinct_colors(len(unique_values))
            value_color_mapping = {x:y for x, y in zip(unique_values, colors)}
            for edge in self.data['edges']:
                edge['color']['color'] = value_color_mapping[edge[color_edges_value]]
        # filter the data currently shown
        filtered_edges = [x['id'] for x in self.filtered_data['edges']]
        self.filtered_data['edges'] = [x for x in self.data['edges'] if x['id'] in filtered_edges]
        graph_data = self.filtered_data
        return graph_data, value_color_mapping

    def _callback_size_edges(self, graph_data, size_edges_value):
        # color option is None, revert back all changes
        if size_edges_value == 'None':
            # revert to default color
            for edge in self.data['edges']:
                edge['width'] = DEFAULT_EDGE_SIZE
        else:
            print("Modifying edge size using ", size_edges_value)
            # fetch the scaling value
            minn = self.scaling_vars['edge'][size_edges_value]['min']
            maxx = self.scaling_vars['edge'][size_edges_value]['max']
            # define the scaling function
            scale_val = lambda x: 20*(x-minn)/(maxx-minn)
            # set the size after scaling
            for edge in self.data['edges']:
                edge['width'] = scale_val(edge[size_edges_value])
        # filter the data currently shown
        filtered_edges = [x['id'] for x in self.filtered_data['edges']]
        self.filtered_data['edges'] = [x for x in self.data['edges'] if x['id'] in filtered_edges]
        graph_data = self.filtered_data
        return graph_data

    def get_color_popover_legend_children(self, node_value_color_mapping={}, edge_value_color_mapping={}):
        """Get the popover legends for node and edge based on the color setting
        """
        # var
        popover_legend_children = []

        # common function
        def create_legends_for(title="Node", legends={}):
            # add title
            _popover_legend_children = [dbc.PopoverHeader(f"{title} legends")]
            # add values if present
            if len(legends) > 0:
                for key, value in legends.items():
                    _popover_legend_children.append(
                        # dbc.PopoverBody(f"Key: {key}, Value: {value}")
                        create_color_legend(key, value)
                        )
            else: # otherwise add filler
                _popover_legend_children.append(dbc.PopoverBody(f"no {title.lower()} colored!"))
            #
            return _popover_legend_children

        # add node color legends
        popover_legend_children.extend(create_legends_for("Node", node_value_color_mapping))
        # add edge color legends
        popover_legend_children.extend(create_legends_for("Edge", edge_value_color_mapping))
        #
        return popover_legend_children

    def create(self, directed=False, vis_opts=None):
        """Create the Jaal app and return it

        Parameter
        ----------
            directed: boolean
                process the graph as directed graph?

            vis_opts: dict
                the visual options to be passed to the dash server (default: None)

        Returns
        -------
            app: dash.Dash
                the Jaal app
        """
        # create the app
        app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP, 'https://cdnjs.cloudflare.com/ajax/libs/vis/4.20.1/vis.min.css'])

        # define layout
        app.layout = get_app_layout(self.data, color_legends=self.get_color_popover_legend_children(), directed=directed, vis_opts=vis_opts)

        # create callbacks to print the data flow map
        @app.callback(
            Output("data-flow-map", "children"),
            [Input("url", "pathname"),
            Input("upload-data", "contents")],
            [State('upload-data', 'filename'),
            State('upload-data', 'last_modified')]
        )
        def data_flow_map(pathname, contents, filename, last_modified):
            if pathname == "/":
                # define layout for the home page
                if contents is not None:
                    dd = [
                        self.parse_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)
                    ]
                    node_df = dd[1]
                    edge_df = dd[0]
                    title = [None]*node_df.shape[0];
                    weight = [None]*node_df.shape[0];
                    for index, i in enumerate(weight):
                        weight[index] = 0;
                        for j in edge_df.itertuples():
                            if (node_df['id'][index] == getattr(j, '_3')) | (node_df['id'][index] == getattr(j, 'to')):
                                weight[index] += 1;
                    node_df['weight'] = weight;

                    for index, i in enumerate(title):
                        title[index] = 'Name:' + node_df['id'][index] + '<br>Number of edges:' + str(node_df['weight'][index]) + '<br>Type:' + node_df['type_desc'][index] + '<br>Create date: ' + str(node_df['create_date'][index]) + '<br>Modify date: ' + str(node_df['modify_date'][index])

                    node_df['title'] = title
                    data2, self.scaling_vars = parse_dataframe(edge_df, node_df)
                    # graph_data = data2
                    self.data = data2
                return [
                    html.Div(
                        visdcc.Network(
                            id = 'graph',
                            data = self.data,
                            options = get_options(directed,vis_opts))
                    )
                ]

        # create callbacks to print case statement, case statement and data catalog
        @app.callback(
            Output("page_for_sub", "children"),
            [Input("url", "pathname"),
            Input("upload-sql-data", "contents")],
            [State('upload-sql-data', 'filename'),
            State('upload-sql-data', 'last_modified')]
        )
        def render_page_content(pathname, contents, filename, last_modified):
            sqlquery = ["""
                   SELECT main_qry.*,
                   subdays.DAYS_OFFER1,
                   subdays.DAYS_OFFER2,
                   subdays.DAYS_OFFER3
            from (
                     SELECT jr.id  as PROJECT_ID,
                            5 * (DATEDIFF(ifnull(lc.creation_date, now()), jr.creation_date) DIV 7)
                                + MID('0123444401233334012222340111123400001234000123440',
                                      7 * WEEKDAY(jr.creation_date)
                                      + WEEKDAY(ifnull(lc.creation_date, now())) + 1, 1)
                                      as LIFETIME,
                            count(distinct
                                  case when jra.application_source = 'VERAMA'
                                    then jra.id else null end)        NUM_APPLICATIONS,
                            count(distinct jra.id) NUM_CANDIDATES,
                            sum(case when jro.stage = 'DEAL' then 1 else 0 end) as NUM_CONTRACTED,
                            sum(ifnull(IS_INTERVIEW, 0)) as NUM_INTERVIEWED,
                            sum(ifnull(IS_PRESENTATION, 0)) as NUM_OFFERED
                     from job_request jr
                              left join job_request_application jra on jr.id = jra.job_request_id
                              left join job_request_offer jro
                              on jro.job_request_application_id = jra.id
                              left join lifecycle lc on lc.object_id=jr.id
                              and lc.lifecycle_object_type='JOB_REQUEST'
                              and lc.event = 'JOB_REQUEST_CLOSED'
                              left join (SELECT jro2.job_request_application_id,
                                                max(case
                                                        when jro2.first_interview_scheduled_date
                                                        is not null then 1
                                                        else 0 end) as IS_INTERVIEW,
                                                max(case when jro2.first_presented_date is not null
                                                then 1 else 0 end) as IS_PRESENTATION
                                         from job_request_offer jro2
                                         group by 1) jrah2
                                         on jra.id = jrah2.job_request_application_id
                              left join client u on jr.client_id = u.id
                     where jr.from_point_break = 0
                       and u.name not in ('Test', 'Demo Client')
                     group by 1, 2) main_qry
                     left join (
                SELECT PROJECT_ID,
                       sum(case when RowNo = 1 then days_to_offer else null end) as DAYS_OFFER1,
                       sum(case when RowNo = 2 then days_to_offer else null end) as DAYS_OFFER2,
                       sum(case when RowNo = 3 then days_to_offer else null end) as DAYS_OFFER3
                from (SELECT PROJECT_ID,
                             days_to_offer,
                             (SELECT count(distinct jro.job_request_application_id)
                              from job_request_offer jro
                                       left join job_request_application jra2
                                       on jro.job_request_application_id = jra2.id
                              where jra2.job_request_id = PROJECT_ID
                                and jro.first_presented_date is not null
                                and jro.first_presented_date <= InitialChangeDate
                             ) as RowNo
                      from (
                               SELECT jr.id                    as PROJECT_ID,
                                      5 * (
                                      DATEDIFF(jro.first_presented_date, jr.creation_date) DIV 7) +
                                      MID('0123444401233334012222340111123400001234000123440',
                                          7 * WEEKDAY(jr.creation_date)
                                          + WEEKDAY(jro.first_presented_date) + 1,
                                          1)                   as days_to_offer,
                                      jro.job_request_application_id,
                                      jro.first_presented_date as InitialChangeDate
                               from presentation pr
                                        left join presentation_job_request_offer pjro
                                        on pr.id = pjro.presentation_id
                                        left join job_request_offer jro
                                        on pjro.job_request_offer_id = jro.id
                                        left join job_request jr on pr.job_request_id = jr.id
                               where jro.first_presented_date is not null) days_sqry) days_final_qry
                group by PROJECT_ID) subdays
                               on subdays.PROJECT_ID = main_qry.PROJECT_ID

                    """]
            
            ctx = dash.callback_context
            if ctx.triggered:
                input_id = ctx.triggered[0]['prop_id'].split('.')[0]
                if input_id == 'upload-sql-data':
                    dd = [
                        self.parse_sql_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)
                    ]
                    sqllist = dd[0]
                    sqlquery = sqllist['sqlscripts'][0]

            # call the function from the file lineage.py at the back-end
            sub_and_ca = []
            if contents is not None:
                dd = [
                        self.parse_sql_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)
                    ]
                sqllist = dd[0]
                # sqlquery = sqllist['sqlscripts'][0]
                sqlquery = sqllist['sqlscripts']
                # sub_and_ca = parse_subquery_and_case(sqlquery)
                sub_and_ca = parse_subquery_and_case2(sqlquery)
            else:
                # sub_and_ca = parse_subquery_and_case(sqlquery)
                sub_and_ca = parse_subquery_and_case2(sqlquery)

            if pathname == "/page-1":
                # case statement list
                return create_case_show2(sub_and_ca[0])

        @app.callback(
            Output("page_for_case", "children"),
            [Input("url", "pathname"),
            Input("upload-sql-data", "contents")],
            [State('upload-sql-data', 'filename'),
            State('upload-sql-data', 'last_modified')]
        )
        def render_page_content(pathname, contents, filename, last_modified):
            sqlquery = ["""
                   SELECT main_qry.*,
                   subdays.DAYS_OFFER1,
                   subdays.DAYS_OFFER2,
                   subdays.DAYS_OFFER3
            from (
                     SELECT jr.id  as PROJECT_ID,
                            5 * (DATEDIFF(ifnull(lc.creation_date, now()), jr.creation_date) DIV 7)
                                + MID('0123444401233334012222340111123400001234000123440',
                                      7 * WEEKDAY(jr.creation_date)
                                      + WEEKDAY(ifnull(lc.creation_date, now())) + 1, 1)
                                      as LIFETIME,
                            count(distinct
                                  case when jra.application_source = 'VERAMA'
                                    then jra.id else null end)        NUM_APPLICATIONS,
                            count(distinct jra.id) NUM_CANDIDATES,
                            sum(case when jro.stage = 'DEAL' then 1 else 0 end) as NUM_CONTRACTED,
                            sum(ifnull(IS_INTERVIEW, 0)) as NUM_INTERVIEWED,
                            sum(ifnull(IS_PRESENTATION, 0)) as NUM_OFFERED
                     from job_request jr
                              left join job_request_application jra on jr.id = jra.job_request_id
                              left join job_request_offer jro
                              on jro.job_request_application_id = jra.id
                              left join lifecycle lc on lc.object_id=jr.id
                              and lc.lifecycle_object_type='JOB_REQUEST'
                              and lc.event = 'JOB_REQUEST_CLOSED'
                              left join (SELECT jro2.job_request_application_id,
                                                max(case
                                                        when jro2.first_interview_scheduled_date
                                                        is not null then 1
                                                        else 0 end) as IS_INTERVIEW,
                                                max(case when jro2.first_presented_date is not null
                                                then 1 else 0 end) as IS_PRESENTATION
                                         from job_request_offer jro2
                                         group by 1) jrah2
                                         on jra.id = jrah2.job_request_application_id
                              left join client u on jr.client_id = u.id
                     where jr.from_point_break = 0
                       and u.name not in ('Test', 'Demo Client')
                     group by 1, 2) main_qry
                     left join (
                SELECT PROJECT_ID,
                       sum(case when RowNo = 1 then days_to_offer else null end) as DAYS_OFFER1,
                       sum(case when RowNo = 2 then days_to_offer else null end) as DAYS_OFFER2,
                       sum(case when RowNo = 3 then days_to_offer else null end) as DAYS_OFFER3
                from (SELECT PROJECT_ID,
                             days_to_offer,
                             (SELECT count(distinct jro.job_request_application_id)
                              from job_request_offer jro
                                       left join job_request_application jra2
                                       on jro.job_request_application_id = jra2.id
                              where jra2.job_request_id = PROJECT_ID
                                and jro.first_presented_date is not null
                                and jro.first_presented_date <= InitialChangeDate
                             ) as RowNo
                      from (
                               SELECT jr.id                    as PROJECT_ID,
                                      5 * (
                                      DATEDIFF(jro.first_presented_date, jr.creation_date) DIV 7) +
                                      MID('0123444401233334012222340111123400001234000123440',
                                          7 * WEEKDAY(jr.creation_date)
                                          + WEEKDAY(jro.first_presented_date) + 1,
                                          1)                   as days_to_offer,
                                      jro.job_request_application_id,
                                      jro.first_presented_date as InitialChangeDate
                               from presentation pr
                                        left join presentation_job_request_offer pjro
                                        on pr.id = pjro.presentation_id
                                        left join job_request_offer jro
                                        on pjro.job_request_offer_id = jro.id
                                        left join job_request jr on pr.job_request_id = jr.id
                               where jro.first_presented_date is not null) days_sqry) days_final_qry
                group by PROJECT_ID) subdays
                               on subdays.PROJECT_ID = main_qry.PROJECT_ID

                    """]
            
            ctx = dash.callback_context
            if ctx.triggered:
                input_id = ctx.triggered[0]['prop_id'].split('.')[0]
                if input_id == 'upload-sql-data':
                    dd = [
                        self.parse_sql_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)
                    ]
                    sqllist = dd[0]
                    sqlquery = sqllist['sqlscripts'][0]

            # call the function from the file lineage.py at the back-end
            sub_and_ca = []
            if contents is not None:
                dd = [
                        self.parse_sql_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)
                    ]
                sqllist = dd[0]
                sqlquery = sqllist['sqlscripts']
                sub_and_ca = parse_subquery_and_case2(sqlquery)
            else:
                sub_and_ca = parse_subquery_and_case2(sqlquery)

            if pathname == "/page-2":
                # define layout for the page-2 page
                return create_case_show2(sub_and_ca[1])

        @app.callback(
            Output("page_for_catalog", "children"),
            [Input("url", "pathname"),
            Input("upload-catalog-data", "contents")],
            [State('upload-catalog-data', 'filename'),
            State('upload-catalog-data', 'last_modified')]
        )
        def render_page_content(pathname, contents, filename, last_modified):
            if pathname == "/page-3":
                if contents is not None:
                    children = [
                        self.parse_catalog_contents(c, n, d) for c, n, d in
                        zip(contents, filename, last_modified)]
                    return children

        # create callbacks to toggle legend popover
        @app.callback(
            Output("color-legend-popup", "is_open"),
            [Input("color-legend-toggle", "n_clicks")],
            [State("color-legend-popup", "is_open")]
        )
        def toggle_popover(n, is_open):
            if n:
                return not is_open
            return is_open

        # create callbacks to toggle hide/show sections - FILTER section
        @app.callback(
            Output("filter-show-toggle", "is_open"),
            [Input("filter-show-toggle-button", "n_clicks")],
            [State("filter-show-toggle", "is_open")]
        )
        def toggle_filter_collapse(n, is_open):
            if n:
                return not is_open
            return is_open

        # create callbacks to toggle hide/show sections - COLOR section
        @app.callback(
            Output("color-show-toggle", "is_open"),
            [Input("color-show-toggle-button", "n_clicks")],
            [State("color-show-toggle", "is_open")]
        )
        def toggle_filter_collapse(n, is_open):
            if n:
                return not is_open
            return is_open

        # create callbacks to toggle hide/show sections - COLOR section
        @app.callback(
            Output("size-show-toggle", "is_open"),
            [Input("size-show-toggle-button", "n_clicks")],
            [State("size-show-toggle", "is_open")]
        )
        def toggle_filter_collapse(n, is_open):
            if n:
                return not is_open
            return is_open

        # create the main callbacks
        @app.callback(
            [Output('graph', 'data'), Output('color-legend-popup', 'children')],
            [Input('search_graph', 'value'),
            Input('filter_nodes', 'value'),
            Input('filter_edges', 'value'),
            Input('color_nodes', 'value'),
            Input('color_edges', 'value'),
            Input('size_nodes', 'value'),
            Input('size_edges', 'value'),
            Input('upload-data', 'contents')],
            [State('upload-data', 'filename'),
            State('upload-data', 'last_modified'),
            State('graph', 'data')]
        )
        def setting_pane_callback(search_text, filter_nodes_text, filter_edges_text,
                    color_nodes_value, color_edges_value, size_nodes_value, size_edges_value, list_of_contents, list_of_names, list_of_dates, graph_data):
            # fetch the id of option which triggered
            ctx = dash.callback_context
            # if its the first call
            if not ctx.triggered:
                print("No trigger")
                return [self.data, self.get_color_popover_legend_children()]
            else:
                # find the id of the option which was triggered
                input_id = ctx.triggered[0]['prop_id'].split('.')[0]
                # perform operation in case of search graph option
                if input_id == "search_graph":
                    graph_data = self._callback_search_graph(graph_data, search_text)
                # In case filter nodes was triggered
                elif input_id == 'filter_nodes':
                    graph_data = self._callback_filter_nodes(graph_data, filter_nodes_text)
                # In case filter edges was triggered
                elif input_id == 'filter_edges':
                    graph_data = self._callback_filter_edges(graph_data, filter_edges_text)
                # If color node text is provided
                if input_id == 'color_nodes':
                    graph_data, self.node_value_color_mapping = self._callback_color_nodes(graph_data, color_nodes_value)
                # If color edge text is provided
                if input_id == 'color_edges':
                    graph_data, self.edge_value_color_mapping = self._callback_color_edges(graph_data, color_edges_value)
                # If size node text is provided
                if input_id == 'size_nodes':
                    graph_data = self._callback_size_nodes(graph_data, size_nodes_value)
                # If size edge text is provided
                if input_id == 'size_edges':
                    graph_data = self._callback_size_edges(graph_data, size_edges_value)
                if input_id == 'upload-data':
                    if list_of_contents is not None:
                        dd = [
                            self.parse_contents(c, n, d) for c, n, d in
                            zip(list_of_contents, list_of_names, list_of_dates)
                        ]
                        node_df = dd[1]
                        edge_df = dd[0]
                        title = [None]*node_df.shape[0];
                        weight = [None]*node_df.shape[0];
                        for index, i in enumerate(weight):
                            weight[index] = 0;
                            for j in edge_df.itertuples():
                                if (node_df['id'][index] == getattr(j, '_3')) | (node_df['id'][index] == getattr(j, 'to')):
                                    weight[index] += 1;
                        node_df['weight'] = weight;

                        for index, i in enumerate(title):
                            title[index] = 'Name:' + node_df['id'][index] + '<br>Number of edges:' + str(node_df['weight'][index]) + '<br>Type:' + node_df['type_desc'][index] + '<br>Create date: ' + str(node_df['create_date'][index]) + '<br>Modify date: ' + str(node_df['modify_date'][index])

                        node_df['title'] = title
                        data2, self.scaling_vars = parse_dataframe(edge_df, node_df)
                        graph_data = data2
            # create the color legend childrens
            color_popover_legend_children = self.get_color_popover_legend_children(self.node_value_color_mapping, self.edge_value_color_mapping)
            # finally return the modified data
            return [graph_data, color_popover_legend_children]
        # return server
        return app

    def plot(self, debug=False, host="127.0.0.1", port="8050", directed=False, vis_opts=None):
        """Plot the Jaal by first creating the app and then hosting it on default server

        Parameter
        ----------
            debug (boolean)
                run the debug instance of Dash?

            host: string
                ip address on which to run the dash server (default: 127.0.0.1)

            port: string
                port on which to expose the dash server (default: 8050)

            directed (boolean):
                whether the graph is directed or not (default: False)

            vis_opts: dict
                the visual options to be passed to the dash server (default: None)
        """
        # call the create_graph function
        app = self.create(directed=directed, vis_opts=vis_opts)
        # run the server
        app.run_server(debug=False, host=host, port=port)