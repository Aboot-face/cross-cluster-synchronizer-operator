# cross-cluster-synchronizer-operator

## Intro

The cross-cluster-sync-operator is designed to be able to sync resources across clusters. I designed this as a way to better administer resources between clusters.

Currently, it supports specifying specific ConfigMaps and Secrets to apply from one source cluster to target clusters.

## Planned Features/Roadmap

### Close goals
1. Support for other simple resources like SA, RBAC, PVC, etc.
2. Monitoring configmaps after a SyncConfig resource is deployed.
3. Namespace monitoring of specific resources.
4. ~~support for specifying specific namespaces for resources (specific configmaps or secrets).~~
5. Containerization with Helm deployment as well as kubeconfig secret handling.

### Far goals
1. Optional Bi-directional syncing (having CCS Operators on each cluster).
2. Handling more complex resources.
3. Auditing and Logging.
4. Better performance and error handling.

Obviously these are not the only goals, but some good ones to start.

## Configuration

Currently, the operator is managed by a CRD: `SyncConfig`

#### Example SyncConfig
```yaml
apiVersion: myoperator.example.com/v1
kind: SyncConfig
metadata:
  name: test-sync-configmap
spec:
  sourceCluster: "cluster1"
  targetClusters:
    - "cluster2"
  resources:
    - kind: "ConfigMap"
      namespace: "test2"
    - kind: "ConfigMap"
      name: "test-configmap2"
      namespace: "test"
  namespaceHandling: "create"
```

This will sync the `test-configmap2` resource in the `test` namespace to the `cluster2` cluster from the `cluster1` cluster. It will also sync all ConfigMaps in the `test2` namespace.
`namespaceHandling` is for if a namespace is not detected, how does the operator handle this. The two valid options are `create` and `fail`. These are pretty self explanitory.

Just keep in mind that **currently** the resources are only synced when the `SyncConfig` CR is applied to the cluster.

#### Cluster Authentication

For authentication to each cluster, you will need a kubeconfig for each. These are placed inside the `./kube` dir currently with the naming convention: `<cluster_name>.kubeconfig`.

Dummy kubeconfigs are inside the `kube/` dir currently to demonstrate.

## Install

Run these commands to download and start the operator:
```git clone https://github.com/Aboot-face/cross-cluster-synchronizer-operator.git CCS-Operator
cd CCS-Operator
kubectl apply -f app/syncconfig.yaml
kopf run app/app.py <-n namespace (optional as it shouldn't really matter)>
```

Then you can configure the kubeconfigs for your clusters using the naming scheme specified above. There is a sample `SyncConfig` in `test/` for you to specify your configuration. 

## Current Testing

I have been currently testing on two minikube clusters. I will have to upgrade this if I want to test an actual cluster-to-cluster deployment through containerization as minikube clusters cannot communicate together.
