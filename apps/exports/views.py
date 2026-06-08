from django.http import HttpResponse
from django.views import View
from apps.matches.models import Match
from apps.exports.services import export_match_json, export_match_csv, export_match_pdf

class MatchExportView(View):
    """
    API endpoint to export match results as JSON, CSV, or PDF.
    URL pattern: /api/matches/<match_id>/export/?format=json|csv|pdf
    """
    def get(self, request, match_id):
        import uuid
        try:
            match_uuid = uuid.UUID(match_id)
            match = Match.objects.get(id=match_uuid)
        except (Match.DoesNotExist, ValueError, TypeError):
            return HttpResponse("Match not found or invalid ID format.", status=404)
            
        export_format = request.GET.get('format', 'json').lower()
        
        if export_format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="match_{match_id}_export.csv"'
            return export_match_csv(match, response)
            
        elif export_format == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="match_{match_id}_export.pdf"'
            return export_match_pdf(match, response)
            
        else: # Default is JSON
            json_data = export_match_json(match)
            response = HttpResponse(json_data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="match_{match_id}_export.json"'
            return response
