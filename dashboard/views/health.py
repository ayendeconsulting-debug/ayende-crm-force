"""
Custom Health Check View
Uses all registered plugins from plugin_dir

Location: dashboard/views/health.py
"""
from django.http import JsonResponse, HttpResponse
from health_check.plugins import plugin_dir


def health_check_view(request):
    """
    Run all registered health checks and return results
    """
    results = {}
    overall_status = 200
    
    for plugin_class, options in plugin_dir._registry:
        plugin = plugin_class(**options)
        
        # Get identifier - use identifier() method if available, otherwise use class name
        if hasattr(plugin, 'identifier'):
            plugin_id = plugin.identifier()
        else:
            plugin_id = plugin_class.__name__
        
        try:
            plugin.run_check()
            results[plugin_id] = {
                'status': 'OK',
                'errors': []
            }
        except Exception as e:
            results[plugin_id] = {
                'status': 'ERROR',
                'errors': [str(e)]
            }
            overall_status = 500
    
    # Return JSON or HTML based on Accept header
    if 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        return JsonResponse(results, status=overall_status)
    
    # Simple HTML response
    html = '<html><head><title>System Health</title><style>'
    html += 'body{font-family:sans-serif;margin:40px;background:#1a1a1a;color:#fff}'
    html += 'h1{color:#4caf50}table{width:100%;border-collapse:collapse}'
    html += 'th,td{padding:12px;text-align:left;border-bottom:1px solid #333}'
    html += 'th{background:#2d2d2d}.ok{color:#4caf50}.error{color:#f44336}'
    html += '</style></head><body>'
    html += '<h1>🔥 System Status 🔥</h1><table><tr><th>Service</th><th>Status</th></tr>'
    
    for service, data in results.items():
        status_class = 'ok' if data['status'] == 'OK' else 'error'
        html += f'<tr><td>{service}</td><td class="{status_class}">{data["status"]}</td></tr>'
    
    html += '</table></body></html>'
    
    return HttpResponse(html, status=overall_status)