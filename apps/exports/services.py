import csv
import json
from decimal import Decimal
from django.http import HttpResponse
from apps.matches.models import Match, MatchPlayer, MatchScore
from apps.rounds.models import Round, Bid, RoundResult

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def get_match_export_data(match):
    """
    Compile a complete dictionary of match details, players, rounds, and scores.
    """
    players = MatchPlayer.objects.filter(match=match).order_by('seat_no')
    player_map = {p.player_id: p.player.name for p in players}
    player_seats = {p.player_id: p.seat_no for p in players}
    
    rounds = Round.objects.filter(match=match).order_by('round_no')
    
    round_data = []
    cumulative_scores = {p_id: Decimal('0.0') for p_id in player_map.keys()}
    
    for r in rounds:
        r_bids = {b.player_id: {'bid': b.bid, 'is_blind': b.is_blind} for b in Bid.objects.filter(round=r)}
        r_results = {res.player_id: {'tricks_won': res.tricks_won, 'score': res.score} for res in RoundResult.objects.filter(round=r)}
        
        player_round_stats = []
        for p_id, p_name in player_map.items():
            pb = r_bids.get(p_id, {'bid': 0, 'is_blind': False})
            pr = r_results.get(p_id, {'tricks_won': 0, 'score': Decimal('0.00')})
            
            cumulative_scores[p_id] += pr['score']
            
            player_round_stats.append({
                'player_id': str(p_id),
                'player_name': p_name,
                'bid': pb['bid'],
                'is_blind': pb['is_blind'],
                'tricks_won': pr['tricks_won'],
                'score': float(pr['score']),
                'cumulative_score': float(cumulative_scores[p_id])
            })
            
        round_data.append({
            'round_id': str(r.id),
            'round_no': r.round_no,
            'trump_card': r.trump_card,
            'status': r.status,
            'locked': r.locked,
            'players': player_round_stats
        })
        
    final_scores = {s.player_id: float(s.total_score) for s in MatchScore.objects.filter(match=match)}
    
    return {
        'match_id': str(match.id),
        'status': match.status,
        'created_at': match.created_at.isoformat() if match.created_at else None,
        'completed_at': match.completed_at.isoformat() if match.completed_at else None,
        'players': [
            {
                'player_id': str(p_id),
                'player_name': name,
                'seat_no': player_seats[p_id],
                'final_score': final_scores.get(p_id, 0.0)
            } for p_id, name in player_map.items()
        ],
        'rounds': round_data
    }

def export_match_json(match):
    """
    Export match data as a JSON string.
    """
    data = get_match_export_data(match)
    return json.dumps(data, indent=2)

def export_match_csv(match, response):
    """
    Write match data as a CSV table to the response.
    """
    data = get_match_export_data(match)
    writer = csv.writer(response)
    
    # Metadata
    writer.writerow(['Match ID', data['match_id']])
    writer.writerow(['Status', data['status']])
    writer.writerow(['Created At', data['created_at']])
    writer.writerow(['Completed At', data['completed_at']])
    writer.writerow([])
    
    # Player Standings
    writer.writerow(['Player Name', 'Seat No', 'Final Score'])
    for p in data['players']:
        writer.writerow([p['player_name'], p['seat_no'], p['final_score']])
    writer.writerow([])
    
    # Round details
    writer.writerow([
        'Round No', 'Trump Card', 'Round Status', 
        'Player Name', 'Bid', 'Is Blind', 'Tricks Won', 
        'Round Score', 'Cumulative Score'
    ])
    
    for r in data['rounds']:
        for p in r['players']:
            writer.writerow([
                r['round_no'], r['trump_card'] or 'N/A', r['status'],
                p['player_name'], p['bid'], p['is_blind'], p['tricks_won'],
                p['score'], p['cumulative_score']
            ])
            
    return response

def export_match_pdf(match, response):
    """
    Write match data as a styled PDF report to the response.
    """
    data = get_match_export_data(match)
    
    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1A237E'), # Navy
        spaceAfter=15
    )
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0D47A1'),
        spaceBefore=15,
        spaceAfter=10
    )
    body_style = styles['Normal']
    
    elements = []
    
    # Document Title
    elements.append(Paragraph("Call Break Companion - Match Report", title_style))
    elements.append(Paragraph(f"<b>Match ID:</b> {data['match_id']}", body_style))
    elements.append(Paragraph(f"<b>Status:</b> {data['status']}", body_style))
    elements.append(Paragraph(f"<b>Date:</b> {data['created_at'][:10] if data['created_at'] else 'N/A'}", body_style))
    elements.append(Spacer(1, 15))
    
    # Standings / Final Scores
    elements.append(Paragraph("Final Standings", section_style))
    standings_data = [['Seat', 'Player Name', 'Final Score']]
    for p in sorted(data['players'], key=lambda x: x['final_score'], reverse=True):
        standings_data.append([
            f"Seat {p['seat_no']}",
            p['player_name'],
            f"{p['final_score']:.2f}"
        ])
        
    standings_table = Table(standings_data, colWidths=[100, 250, 150])
    standings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A237E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#B0BEC5')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    elements.append(standings_table)
    elements.append(Spacer(1, 20))
    
    # Round Breakdown
    elements.append(Paragraph("Round-by-Round Breakdown", section_style))
    
    # Table headers
    headers = ['Round', 'Trump', 'Player', 'Bid', 'Blind?', 'Tricks', 'Round Score', 'Total']
    round_rows = [headers]
    
    for r in data['rounds']:
        for i, p in enumerate(r['players']):
            round_cell = f"Round {r['round_no']}" if i == 0 else ""
            trump_cell = (r['trump_card'] or 'N/A') if i == 0 else ""
            round_rows.append([
                round_cell,
                trump_cell,
                p['player_name'],
                p['bid'],
                'Yes' if p['is_blind'] else 'No',
                p['tricks_won'],
                f"{p['score']:.2f}",
                f"{p['cumulative_score']:.2f}"
            ])
            
    round_table = Table(round_rows, colWidths=[65, 55, 120, 45, 45, 45, 80, 75])
    
    # Construct alternating color background styles for groups of 4 rows (per round)
    tbl_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0D47A1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CFD8DC')),
    ]
    
    # Color alternate rounds
    for r_idx in range(len(data['rounds'])):
        bg_color = colors.HexColor('#FFFFFF') if r_idx % 2 == 0 else colors.HexColor('#ECEFF1')
        start_row = 1 + r_idx * 4
        end_row = start_row + 3
        tbl_styles.append(('BACKGROUND', (0, start_row), (-1, end_row), bg_color))
        # Merge first two columns for each round
        tbl_styles.append(('SPAN', (0, start_row), (0, end_row)))
        tbl_styles.append(('SPAN', (1, start_row), (1, end_row)))
        
    round_table.setStyle(TableStyle(tbl_styles))
    elements.append(round_table)
    
    # Build Document
    doc.build(elements)
    return response
