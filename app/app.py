import kopf
import kubernetes
import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def fetch_resources(api_instance, kind, name=None, namespace=None):
    """
    Fetch resources based on kind, name, and namespace.
    If name is None, fetch all resources of the kind in the namespace.
    If namespace is None, attempt to fetch resources across all namespaces (if supported).
    """
    resources = []
    try:
        if kind.lower() == "configmap":
            if name:
                resources = [api_instance.read_namespaced_config_map(name=name, namespace=namespace)]
            elif namespace:
                resources = api_instance.list_namespaced_config_map(namespace=namespace).items
            else:
                resources = api_instance.list_config_map_for_all_namespaces().items
        elif kind.lower() == "secret":
            if name:
                resources = [api_instance.read_namespaced_secret(name=name, namespace=namespace)]
            elif namespace:
                resources = api_instance.list_namespaced_secret(namespace=namespace).items
            else:
                resources = api_instance.list_secret_for_all_namespaces().items
    except ApiException as e:
        print(f"Error fetching {kind}{'s' if not name else ''}{' in namespace ' + namespace if namespace else ''}: {e}")
    return resources

async def ensure_namespace_exists(api_instance, namespace, handling):
    """
    ensure that the namespace exists. 
    """
    try:
        api_instance.read_namespace(name=namespace)
    except ApiException as e:
        if e.status == 404 and handling == "create":
            ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            api_instance.create_namespace(body=ns)
        elif handling == "fail":
            raise kopf.TemporaryError(f"Namespace '{namespace}' does not exist in target cluster, and 'namespaceHandling' is set to 'fail'.", delay=60)

def get_kubernetes_api(cluster_name="default"):
    """
    get the kubernetes api based on the source or target kubeconfigs
    """
    kubeconfig_path = os.path.join("kube/", f"{cluster_name}.kubeconfig")
    config.load_kube_config(kubeconfig_path)
    return client.CoreV1Api()

def prepare_resource_for_sync(resource):
    """
    prepare resource for syncing by removing certain cluster specific metadata
    """
    resource.metadata.resource_version = None
    resource.metadata.uid = None
    resource.metadata.creation_timestamp = None
    resource.metadata.managed_fields = None
    return resource

async def sync_resource(source_cluster, resource_kind, target_clusters, namespace_handling, resource_spec):
    """
    sync defined resources based on a SyncConfig CR
    """
    source_api = get_kubernetes_api(source_cluster)
    resource_name = resource_spec.get('name', None)
    namespace = resource_spec.get('namespace', None)

    resources = fetch_resources(source_api, resource_kind, resource_name, namespace)
    for resource in resources:
        if resource is None:
            continue  # Skip if no resource found

        resource = prepare_resource_for_sync(resource)
        for cluster in target_clusters:
            target_api = get_kubernetes_api(cluster)
            await ensure_namespace_exists(target_api, namespace or resource.metadata.namespace, namespace_handling)

            try:
                if resource_kind.lower() == "configmap":
                    target_api.create_namespaced_config_map(namespace=namespace or resource.metadata.namespace, body=resource)
                elif resource_kind.lower() == "secret":
                    target_api.create_namespaced_secret(namespace=namespace or resource.metadata.namespace, body=resource)
                print(f"Synchronized {resource_kind} '{resource.metadata.name}' to namespace '{namespace or resource.metadata.namespace}' in '{cluster}'")
            except ApiException as e:
                if e.reason == 'Conflict':
                    print(f"Failed to synchronize {resource_kind} '{resource.metadata.name}' to namespace '{namespace or resource.metadata.namespace}' in '{cluster}' because of a conflict. Please check the namespace on the target cluster.")
                else:
                    print(f"Failed to synchronize {resource_kind} '{resource.metadata.name}' to namespace '{namespace or resource.metadata.namespace}' in '{cluster}': {e}")

@kopf.on.create('myoperator.example.com', 'v1', 'syncconfigs')
@kopf.on.update('myoperator.example.com', 'v1', 'syncconfigs')
async def handle_syncconfig(spec, **kwargs):
    source_cluster = spec.get('sourceCluster')
    target_clusters = spec.get('targetClusters', [])
    namespace_handling = spec.get('namespaceHandling', "fail")
    resources = spec.get('resources', [])

    for resource_spec in resources:
        resource_kind = resource_spec.get('kind')
        await sync_resource(source_cluster, resource_kind, target_clusters, namespace_handling, resource_spec)
