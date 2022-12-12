# import
from jaal import Jaal
from jaal.datasets import load_got
import os
import pandas as pd

def load_get(filter_conections_threshold=10):
    """Load the first book of the Got Dataset
    Parameters
    -----------
    filter_conections_threshold: int
        keep the connections in GoT dataset with weights greater than this threshold 
    """
    # resolve path
    this_dir, _ = os.path.split(__file__)
    # load the edge and node data
    edge_df = pd.read_csv(os.path.join(this_dir, "edge.csv"))
    node_df = pd.read_csv(os.path.join(this_dir, "node.csv"))
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
    # return 
    return edge_df, node_df
edge_df, node_df = load_get()

# init Jaal and run server (with opts)
Jaal(edge_df, node_df).plot(vis_opts={
                                    # 'height': '1000px', # For laptop
                                    'height': '1300px', # For computer
                                    # 'width': '100%', # For laptop
                                    'width': '115%', # For computer
                                    'interaction':{'hover': True,
                                        # 'hideEdgesOnDrag': True,
                                        'multiselect': True
                                    }, # turn on-off the hover
                                    'manipulation': {
                                        'enabled': True
                                    },
                                    'physics': False,
                                    # 'clickToUse': True,
                                    # 'nodes': {'chosen': True,
                                    # 'label': 'tttt',
                                    # 'title':'fdfdf',
                                    # }
                                    })