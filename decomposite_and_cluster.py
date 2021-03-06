"""
The extension of this script is ".py" since github does not interpret that of Jupyter notebook.
You can modify the file name as "your_favorite_name.ipynb" and load on your Jupyter system.
"""


import sys, datetime, pathlib, re
import plotly
import plotly.graph_objs as go
import plotly.offline
import sklearn.cluster
import pandas as pd
import numpy as np
import sklearn.cluster
import argparse
import os
import json

try:
    import umap.umap_ as umap
except:
    import umap

parser = argparse.ArgumentParser()
parser.add_argument('-i', default=['input.fcs', ], nargs='+')
parser.add_argument('--outdir', default='out', metavar='output directory')
parser.add_argument('--verbose', action='store_true')
parser.add_argument('-n', type=int, default=4, metavar='number', help='number of clusters')
parser.add_argument('--decomposition', default='umap', metavar='umap/tsne/pca')
parser.add_argument('--clustering', default='dbscan', metavar='dbscan/kmeans/agglomerative')
parser.add_argument('--sampling', type=int, default=0)
parser.add_argument('--params', nargs='+')
args = parser.parse_args()
filenames = args.i
dstdir = args.outdir
verbose = args.verbose
params = {}
decomposition_algorithms = ['TSNE', 'PCA', 'UMAP'] 
# clustering_methods = ['KMeans', 'Agglomerative', 'DBSCAN']
clustering_methods = ['KMEANS', 'AGGLOMERATIVE', 'DBSCAN']

for param in args.params:
    items = param.split('=', 1)
    if len(items) == 1:
        params[items[0]] = 1
    else:
        params[items[0]] = float(items[1])

decomposition = args.decomposition.upper()
if decomposition not in decomposition_algorithms:
    raise Exception('Decomposition algorithm {} is not supported'.format(decomposition))
clustering = args.clustering.upper()
if clustering not in clustering_methods:
    raise Exception('Clustering algorithm {} is not supported'.format(clustering))

#filename = 'your/fcs/or/tsv/path'

# Algorithm options

##### Parameters

n_clusters = 4

sampling_mode = args.sampling > 0 # Set as False if you display all points

# Decomposite and cluster results of each cell
if os.path.exists(dstdir) is False:
    os.makedirs(dstdir)

filename_results = os.path.join(dstdir, "results.tsv")
# Average color intensity of each cluster
filename_clusters = os.path.join(dstdir, "clusters.tsv")
filename_graph = os.path.join(dstdir, 'graph.html')
filename_info = os.path.join(dstdir, 'run_info.json')
#verbose = True

# algorithm = 'tSNE'
# algorithm = 'PCA'
# algorithm = 'UMAP'

# clustering = None
# clustering = 'KMeans'
# clustering = 'Agglomerative'
# clustering = "DBSCAN"

# if algorithm is not None and algorithm not in decomposition_algorithms:
#     raise Exception('Decomposition algorithm {} is not supported'.format(algrorithm))
# if clustering is not None and clustering not in clustering_methods:
#     raise Exception('Clustering algorithm {} is not supported'.format(clustering))

logarithm_mode = False
axes = 0, 1, 2
if sampling_mode:
    max_samples = args.sampling
else:
    max_samples = 0


n_components = max(axes) + 1 # dimension of decomposition

def generate_test_data(n_samples=1000, n_dimensions=4, n_groups=4):
    centers = [(0,0,0,0,0), (3,3,0,1,2), (-2,0,4,-1,-4), (1, -5, 3, 4,2)]
    n_dimensions = min(n_dimensions, len(centers[0]))
    n_groups = min(n_groups, len(centers))
    deviations = [2, .5, 1.2, .9][0:n_groups]
    data = []
    labels = []
    i = 0
    group = 0
    while group < n_groups and i < n_samples:
        stop = i + n_samples // n_groups
        labels += [group] * (stop - i)
        dv = deviations[group]
        center = centers[group]
        for j in range(i, stop):
            vals = [np.random.normal(center[k], dv) for k in range(n_dimensions)]
            data.append(vals)
            pass
        i = stop
        group += 1
        pass
    return np.array(data).T, labels

if len(filenames) == 0:
    n_groups = 4
    n_dim = 5
    n_samples = 1000
    analysis_title = "{} random sample {} clusters, {} dimensions".format(n_samples, n_groups, n_dim)

    data, labels = generate_test_data(n_samples, n_dim, n_groups=n_clusters)
    sample_names = [str(l) for l in labels]
else:
    analysis_title = pathlib.Path(filenames[0]).stem
    dataset = []
    labelset = []
    sample_names = []
    for filename in filenames:
        if verbose:
            sys.stderr.write("{} loading file : {}\n".format(datetime.datetime.now().strftime("[%H:%M:%S]"), filename))
        if filename.endswith(".fcs"):
            import fcsparser
            meta, data = fcsparser.parse(filename)
            data = data.T
            color2name = {}
            nondata_columns = ['EQBeads', 'Time', 'Width', 'Event']
            for key, val in meta.items():
                if isinstance(val, str) is False:
                    continue
                m = re.match("\\$(\\w\\d+)N", key)
                if m:
                    color_code = m.group(1)
                    color_name_code = "$" + color_code + "S"
                    if color_name_code in meta:
                        name = meta[color_name_code]
                        if name in nondata_columns: 
                            continue
                        color2name[val] = meta[color_name_code]
            applicable = [index for index in data.index if index in color2name]
            names = [color2name[n_] for n_ in applicable]
            data = data.loc[applicable]
            data.index = names
        else:
            if filename.endswith('.csv'):
                sep = ','
            else:
                sep = '\t'
            data = pd.read_csv(filename, sep=sep, index_col=0)
        if len(dataset) > 0:
            datum = dataset[0]
            antibodies = set(data.index)
            incompatible = len(antibodies) == data.shape[1]
            for index in datum.index:
                if index not in antibodies:
                    incompatible = True
                    break
            if incompatible:
                raise Exception('{} is not compatible with the others'.format(filename.stem))
        # labels = [0] * data.shape[0]
        columns_ = []
        for i in range(data.shape[1]):
            start_ = len(sample_names)
            colname = 'C{}'.format(i + 1 + start_)
            sample_names.append(colname)
            columns_.append(colname)
        data.columns = columns_
        dataset.append(data)
        # labelset.append(labels)
    # print(data.index) # antibodies
    # print(labels)
    # print(sample_names)
    data = pd.concat(dataset, axis=1)
    if max_samples > 0 and max_samples < data.shape[1]:
        if verbose: sys.stderr.write('sampling {} from {} cells\n'.format(max_samples, data.shape[1]))
        columns_ = list(data.columns)
        np.random.shuffle(columns_)
        data = data[columns_[0:max_samples]]
    labels = np.arange(data.shape[0])

    # data, labels = combine_data(dataset, labelset)
    # sample_names = ' + '.join(sample_name_set)

n_samples = data.shape[1]

if filename_info is not None:
    runinfo = {'parameters':params, 'input':filenames, 
    'clustering':clustering, 'decomposition':decomposition,'output':dstdir,
    'sampling':args.sampling, 'size':n_samples, 'features':list(data.index),
    'n_cells':data.shape[1], 'n_features':data.shape[0]}
    print(runinfo)
    with open(filename_info, 'w') as fo:
        fo.write(json.dumps(runinfo))

if logarithm_mode:
    minimum_value = 0.1
    data[data<minimum_value] = minimum_value
    data = np.log(data)

# Decomposition
if verbose and decomposition is not None:
    sys.stderr.write("{} decompose using {}\n".format(datetime.datetime.now().strftime("[%H:%M:%S]"), decomposition))

if decomposition == "TSNE":
    if n_components == 2:
        import MulticoreTSNE
        tsne = MulticoreTSNE.MulticoreTSNE(n_components=n_components, n_jobs=8)
        res = tsne.fit_transform(data.T)
    else:
        import sklearn.manifold
        tsne = sklearn.manifold.TSNE(n_components=n_components)
        res = tsne.fit_transform(data.T)
elif decomposition == "PCA":
    import sklearn.decomposition
    ipca = sklearn.decomposition.IncrementalPCA(n_components=n_components)
    res = ipca.fit_transform(data.T)
elif decomposition == 'UMAP':
    res = umap.UMAP(n_components=n_components).fit_transform(data.T)
else: # no decomposition, display raw data
    res = data.T.values
    pass

# Clustering
if verbose and clustering is not None:
    sys.stderr.write("{} cluster using {}\n".format(datetime.datetime.now().strftime("[%H:%M:%S]"), clustering))

if clustering == "DBSCAN":
    dbscan = sklearn.cluster.DBSCAN(n_jobs=4, eps=params.get('eps', 0.5), min_samples=params.get('min_samples', 5))
    dbscan.fit(res)#data.T)
    clustered = dbscan.labels_
elif clustering == 'KMEANS':
    kmeans = sklearn.cluster.KMeans(n_clusters=n_clusters, n_jobs=4)
    kmeans.fit_predict(res)#data.T)
    clustered = kmeans.labels_
elif clustering == 'AGGLOMERATIVE':
    aggl = sklearn.cluster.AgglomerativeClustering(n_clusters=n_clusters)
    aggl.fit_predict(res)#data.T)
    clustered = aggl.labels_
else: # no clustering
    clustered = labels
    pass

if filename_results is not None:
    with open(filename_results, "w") as fo:
        fo.write("ID")
        dec = "" if clustering is None else clustering
        for i in range(n_components):
            fo.write("\t{}{}".format(dec, i + 1))
        fo.write("\tCluster\n")
        for i, X in enumerate(res):
            fo.write(str(sample_names[i]))
            for x in X:
                fo.write("\t{}".format(x))
            fo.write("\t{}\n".format(clustered[i]))
if filename_clusters is not None:
    num_sets = max(clustered) + 1
    num_elements = data.shape[0]
    accum = np.zeros((num_sets, num_elements))
    num_items = np.zeros(num_sets, dtype=np.int)
    values = data.values
    for i, c in enumerate(clustered):
        if c >= 0:
            num_items[c] += 1
            for j in range(num_elements):
                accum[c][j] += values[j][i]
    with open(filename_clusters, "w") as fo:
        fo.write("Cluster\tNum")
        for index in data.index:
            fo.write("\t{}".format(index))
        fo.write("\n")
        for i in range(num_sets):
            n = num_items[i]
            if n == 0: continue
            fo.write("{}\t{}".format(i + 1, n))
            for v in accum[i]:
                fo.write("\t{:.1f}".format(v / n))
            fo.write("\n")
            
# Prepare diagram
if verbose and clustering is not None:
    sys.stderr.write("{} generating a diagram\n".format(datetime.datetime.now().strftime("[%H:%M:%S]")))

traces = []
given_labels = list(set(clustered))
n_clusters = len(given_labels)
for i in range(n_clusters):
    cluster = given_labels[i]
    indices = []
    for j in range(n_samples):
        if clustered[j] == cluster:
            indices.append(j)
    if len(indices) > 0:
        points = res[indices]
        if len(axes) == 2:
            traces.append(go.Scattergl(mode='markers', x=points[:,axes[0]], y=points[:,axes[1]]))
        elif len(axes) == 3:
            name = 'unclustered' if cluster < 0 else 'C {} ({})'.format(cluster + 1, points.shape[0])
            traces.append(go.Scatter3d(mode="markers", name=name, 
                                       x=points[:,axes[0]], y=points[:,axes[1]], z=points[:,axes[2]], marker=dict(size=2)))
        else:
            raise Exception('invalid number of components, 2 or 3 is allowed')
        pass
    pass

# Generate figure
if len(traces) == 0:
    raise Exception('no clusters detected')
else:
    # plotly.offline.init_notebook_mode(connected=True)

    titles = ["{}{}".format(decomposition if decomposition is not None else 'Raw', axis + 1) for axis in axes]
    if n_components == 3:
        layout = go.Layout(title=analysis_title, scene=dict(xaxis=dict(title=titles[0]), yaxis=dict(title=titles[1]), zaxis=dict(title=titles[2])))
    else:
        layout = go.Layout(title=analysis_title, xaxis=dict(title=titles[0]), yaxis=dict(title=titles[1]))
    fig = go.Figure(traces, layout)
    # plotly.offline.iplot(fig)
    # print(fig)
    plotly.offline.plot(fig, filename=filename_graph) # 'jupyter_out.html')
