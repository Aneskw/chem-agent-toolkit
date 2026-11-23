"""Storage and execution-time arithmetic used by regression checks."""
import http.client
import io
import json
import re


def engine_df(endpoint):
    prefix = 'npipe:////./pipe/'
    if not endpoint.startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_.-]+', endpoint[len(prefix):]):
        raise ValueError('Storage sampler supports the current local Windows Docker named pipe only')
    stream = open('\\\\.\\pipe\\' + endpoint[len(prefix):], 'r+b', buffering=0)
    class Pipe:
        def makefile(self, mode):
            # Raw named-pipe reads may be short; HTTP chunk parsing needs buffering.
            return io.BufferedReader(stream)
    try:
        stream.write(b'GET /system/df HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = http.client.HTTPResponse(Pipe()); response.begin()
        with response:
            if response.status != 200:
                raise ValueError('Docker /system/df HTTP ' + str(response.status))
            return json.loads(response.read())
    finally:
        if not stream.closed: stream.close()


def storage_summary(data):
    # Unknown/negative values remain unknown; never invent zero disk usage.
    size = data.get('LayersSize')
    def usage(key):
        value=data.get(key)
        return {k:v for k,v in value.items() if v is None or isinstance(v,(int,float,bool,str))} if isinstance(value,dict) else None
    return {'image_layers_bytes': size if isinstance(size,int) and size >= 0 else None,
            'image_ids': sorted(i['Id'] for i in data.get('Images') or []),
            'build_cache_records': len(data.get('BuildCache') or []),
            'build_cache_usage': usage('BuildCacheUsage'),
            'image_usage': usage('ImageUsage'),
            'container_usage': usage('ContainerUsage'), 'volume_usage': usage('VolumeUsage')}


def storage_delta(before, after):
    a,b = before['summary'],after['summary']
    cache_a=(a.get('build_cache_usage') or {}).get('TotalSize')
    cache_b=(b.get('build_cache_usage') or {}).get('TotalSize')
    return {'image_layers_bytes': (b['image_layers_bytes']-a['image_layers_bytes']
                                  if a['image_layers_bytes'] is not None and b['image_layers_bytes'] is not None else None),
            'new_image_ids': sorted(set(b['image_ids'])-set(a['image_ids'])),
            'removed_image_ids': sorted(set(a['image_ids'])-set(b['image_ids'])),
            'build_cache_records': b['build_cache_records']-a['build_cache_records'],
            'build_cache_reported_bytes': cache_b-cache_a if isinstance(cache_a,int) and isinstance(cache_b,int) else None,
            'desktop_filesystem_used_bytes': (after['filesystem_used_bytes']-before['filesystem_used_bytes']
                if after['filesystem_used_bytes'] is not None and before['filesystem_used_bytes'] is not None else None)}


def case_timings(report):
    """These fixed atom-map workloads have business checks in both origins.

Authored chemical checks are mapped to interface-layer cases by the pipeline;
they must not disappear from the business-time total just because of that label.
"""
    wall=report.get('case_wall_seconds',{})
    behavior=sum(wall.get(c['name'],0) for c in report['cases'] if c['layer']=='behavior')
    authored=sum(wall.get(c['name'],0) for c in report['cases'] if c.get('origin')=='authored_check' and c['layer']!='behavior')
    return {'model_behavior_cases':behavior,'authored_business_checks':authored,
            'business_cases':behavior+authored,'all_cases':sum(wall.values())}
