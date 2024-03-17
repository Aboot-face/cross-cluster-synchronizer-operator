import kopf
import kubernetes
import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def ensure_namespace_exists(api_instance, namespace, handling):
    try:
        api_instance.read_namespace(name=namespace)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            if handling == "create":
                # attempt to create the namespace
                ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
                api_instance.create_namespace(body=ns)
            elif handling == "fail":
                raise kopf.TemporaryError(f"Namespace '{namespace}' does not exist in target cluster, and 'namespaceHandling' is set to 'fail'.", delay=60)

def get_kubernetes_api(cluster_name="default"):
    kubeconfig_path = os.path.join("kube/", f"{cluster_name}.kubeconfig")
    config.load_kube_config(kubeconfig_path)
    return client.CoreV1Api()

async def sync_resource(source_cluster, resource_kind, resource_name, target_clusters, namespaces, namespace_handling="fail"):
    source_api = get_kubernetes_api(source_cluster)

    for namespace in namespaces or ["default"]:
        resource_body = None

        # fetch the resource from the source cluster
        try:
            if resource_kind.lower() == "configmap":
                resource_body = source_api.read_namespaced_config_map(name=resource_name, namespace=namespace)
            elif resource_kind.lower() == "secret":
                resource_body = source_api.read_namespaced_secret(name=resource_name, namespace=namespace)
        except ApiException as e:
            print(f"Failed to fetch {resource_kind}/{resource_name} from namespace {namespace} in {source_cluster}: {e}")
            continue

        # if resource_body is None, skip synchronization for this resource
        if resource_body is None:
            print(f"{resource_kind} '{resource_name}' not found in namespace '{namespace}' of source cluster '{source_cluster}'. Skipping...")
            continue

        # defore proceeding, ensure resource_version is not set for target object creation
        if hasattr(resource_body, "metadata") and resource_body.metadata:
            resource_body.metadata.resource_version = None

        # synchronize the resource to each target cluster
        for cluster in target_clusters:
            target_api = get_kubernetes_api(cluster)
            ensure_namespace_exists(target_api, namespace, namespace_handling)
            try:
                if resource_kind.lower() == "configmap":
                    target_api.create_namespaced_config_map(namespace=namespace, body=resource_body)
                elif resource_kind.lower() == "secret":
                    target_api.create_namespaced_secret(namespace=namespace, body=resource_body)
                print(f"Synchronized {resource_kind}/{resource_name} to namespace {namespace} in {cluster}")
            except ApiException as e:
                print(f"Failed to synchronize {resource_kind}/{resource_name} to namespace {namespace} in {cluster}: {e}")

@kopf.on.create('myoperator.example.com', 'v1', 'syncconfigs')
@kopf.on.update('myoperator.example.com', 'v1', 'syncconfigs')
async def handle_syncconfig(spec, **kwargs):
    source_cluster = spec.get('sourceCluster')
    target_clusters = spec.get('targetClusters', [])
    namespaces = spec.get('namespaces', None) 
    namespace_handling = spec.get('namespaceHandling', "fail")
    resources = spec.get('resources', [])
    
    for resource in resources:
        resource_kind = resource.get('kind')
        resource_name = resource.get('name')
        await sync_resource(source_cluster, resource_kind, resource_name, target_clusters, namespaces, namespace_handling)


