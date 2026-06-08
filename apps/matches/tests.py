import uuid
import threading
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from apps.matches.models import Player, Match, MatchPlayer, MatchScore
from apps.rounds.models import Round, Bid, RoundResult

class MatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_match_resolves_players(self):
        # Create match by passing player names
        payload = {
            "players": ["Alice", "Bob", "Charlie", "David"]
        }
        response = self.client.post("/api/matches/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "READY")
        
        # Verify players were created in DB
        self.assertEqual(Player.objects.count(), 4)
        self.assertTrue(Player.objects.filter(name="Alice").exists())
        
        # Verify seat numbers
        match_id = response.data["id"]
        match_players = MatchPlayer.objects.filter(match_id=match_id).order_by('seat_no')
        self.assertEqual(len(match_players), 4)
        self.assertEqual(match_players[0].player.name, "Alice")
        self.assertEqual(match_players[0].seat_no, 1)
        self.assertEqual(match_players[3].player.name, "David")
        self.assertEqual(match_players[3].seat_no, 4)
        
        # Verify scores initialized
        scores = MatchScore.objects.filter(match_id=match_id)
        self.assertEqual(scores.count(), 4)
        for s in scores:
            self.assertEqual(float(s.total_score), 0.0)

    def test_start_match_creates_round_one(self):
        # Setup match
        payload = {"players": ["Alice", "Bob", "Charlie", "David"]}
        res = self.client.post("/api/matches/", payload, format="json")
        match_id = res.data["id"]
        
        # Start match
        start_res = self.client.post(f"/api/matches/{match_id}/start/")
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.data["match_status"], "BIDDING")
        
        # Verify Round 1 created
        self.assertEqual(Round.objects.filter(match_id=match_id).count(), 1)
        r1 = Round.objects.get(match_id=match_id, round_no=1)
        self.assertEqual(r1.status, "BIDDING")
        self.assertFalse(r1.locked)

    def test_match_trump_suit_lifecycle(self):
        # Setup match
        payload = {"players": ["Alice", "Bob", "Charlie", "David"]}
        res = self.client.post("/api/matches/", payload, format="json")
        match_id = res.data["id"]
        
        # Verify default trump suit
        self.assertEqual(res.data["trump_suit"], "Spades ♠")
        
        # Update trump suit via PATCH
        patch_payload = {"trump_suit": "Hearts ♥"}
        patch_res = self.client.patch(f"/api/matches/{match_id}/", patch_payload, format="json")
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["trump_suit"], "Hearts ♥")
        
        # Verify saved in DB
        match_db = Match.objects.get(id=match_id)
        self.assertEqual(match_db.trump_suit, "Hearts ♥")


class MatchSyncTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.p1 = Player.objects.create(id=uuid.uuid4(), name="Alice")
        self.p2 = Player.objects.create(id=uuid.uuid4(), name="Bob")
        self.p3 = Player.objects.create(id=uuid.uuid4(), name="Charlie")
        self.p4 = Player.objects.create(id=uuid.uuid4(), name="David")
        self.match_id = uuid.uuid4()

    def test_sync_new_match(self):
        payload = {
            "id": str(self.match_id),
            "version": 1,
            "status": "PLAYING",
            "trump_suit": "Spades ♠",
            "players": [
                {"id": str(self.p1.id), "name": "Alice", "seat_no": 1},
                {"id": str(self.p2.id), "name": "Bob", "seat_no": 2},
                {"id": str(self.p3.id), "name": "Charlie", "seat_no": 3},
                {"id": str(self.p4.id), "name": "David", "seat_no": 4},
            ],
            "rounds": [
                {
                    "id": str(uuid.uuid4()),
                    "round_no": 1,
                    "status": "COMPLETE",
                    "locked": True,
                    "trump_card": "Spades",
                    "bids": [
                        {"player_id": str(self.p1.id), "bid": 3, "is_blind": False},
                        {"player_id": str(self.p2.id), "bid": 4, "is_blind": False},
                        {"player_id": str(self.p3.id), "bid": 2, "is_blind": False},
                        {"player_id": str(self.p4.id), "bid": 4, "is_blind": False},
                    ],
                    "results": [
                        {"player_id": str(self.p1.id), "tricks_won": 3},
                        {"player_id": str(self.p2.id), "tricks_won": 4},
                        {"player_id": str(self.p3.id), "tricks_won": 2},
                        {"player_id": str(self.p4.id), "tricks_won": 4},
                    ]
                }
            ]
        }
        response = self.client.post("/api/matches/sync/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["synced"][0]["status"], "success")
        self.assertEqual(response.data["synced"][0]["version"], 1)

        # Verify DB state
        match = Match.objects.get(id=self.match_id)
        self.assertEqual(match.version, 1)
        self.assertEqual(match.status, "PLAYING")

        score1 = MatchScore.objects.get(match=match, player=self.p1)
        self.assertEqual(float(score1.total_score), 30.00)

    def test_sync_outdated_version_ignored(self):
        match = Match.objects.create(id=self.match_id, version=3, status="PLAYING")
        MatchPlayer.objects.create(match=match, player=self.p1, seat_no=1)
        MatchPlayer.objects.create(match=match, player=self.p2, seat_no=2)
        MatchPlayer.objects.create(match=match, player=self.p3, seat_no=3)
        MatchPlayer.objects.create(match=match, player=self.p4, seat_no=4)

        payload = {
            "id": str(self.match_id),
            "version": 2,
            "status": "MATCH_COMPLETE",
            "players": [
                {"id": str(self.p1.id), "name": "Alice"},
                {"id": str(self.p2.id), "name": "Bob"},
                {"id": str(self.p3.id), "name": "Charlie"},
                {"id": str(self.p4.id), "name": "David"},
            ]
        }
        response = self.client.post("/api/matches/sync/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["synced"][0]["status"], "skipped")
        self.assertIn("newer version", response.data["synced"][0]["message"])

        # Verify DB is unchanged
        match.refresh_from_db()
        self.assertEqual(match.version, 3)
        self.assertEqual(match.status, "PLAYING")

    def test_sync_locked_round_is_immutable(self):
        match = Match.objects.create(id=self.match_id, version=1, status="PLAYING")
        MatchPlayer.objects.create(match=match, player=self.p1, seat_no=1)
        MatchPlayer.objects.create(match=match, player=self.p2, seat_no=2)
        MatchPlayer.objects.create(match=match, player=self.p3, seat_no=3)
        MatchPlayer.objects.create(match=match, player=self.p4, seat_no=4)

        r1 = Round.objects.create(match=match, round_no=1, status="COMPLETE", locked=True)
        Bid.objects.create(round=r1, player=self.p1, bid=3)
        RoundResult.objects.create(round=r1, player=self.p1, tricks_won=3, score=30.00)

        payload = {
            "id": str(self.match_id),
            "version": 2,
            "status": "PLAYING",
            "players": [
                {"id": str(self.p1.id), "name": "Alice", "seat_no": 1},
                {"id": str(self.p2.id), "name": "Bob", "seat_no": 2},
                {"id": str(self.p3.id), "name": "Charlie", "seat_no": 3},
                {"id": str(self.p4.id), "name": "David", "seat_no": 4},
            ],
            "rounds": [
                {
                    "id": str(r1.id),
                    "round_no": 1,
                    "status": "COMPLETE",
                    "locked": True,
                    "trump_card": "Spades",
                    "bids": [
                        {"player_id": str(self.p1.id), "bid": 5, "is_blind": False},
                    ],
                    "results": [
                        {"player_id": str(self.p1.id), "tricks_won": 5},
                    ]
                }
            ]
        }
        response = self.client.post("/api/matches/sync/", payload, format="json")
        self.assertEqual(response.status_code, 200)

        # Verify Round 1 details in DB were not overwritten
        bid = Bid.objects.get(round=r1, player=self.p1)
        self.assertEqual(bid.bid, 3)

        res = RoundResult.objects.get(round=r1, player=self.p1)
        self.assertEqual(res.tricks_won, 3)

    def test_concurrent_syncs_handled_gracefully(self):
        payload_a = {
            "id": str(self.match_id),
            "version": 2,
            "status": "PLAYING",
            "players": [
                {"id": str(self.p1.id), "name": "Alice", "seat_no": 1},
                {"id": str(self.p2.id), "name": "Bob", "seat_no": 2},
                {"id": str(self.p3.id), "name": "Charlie", "seat_no": 3},
                {"id": str(self.p4.id), "name": "David", "seat_no": 4},
            ]
        }
        payload_b = {
            "id": str(self.match_id),
            "version": 2,
            "status": "MATCH_COMPLETE",
            "players": [
                {"id": str(self.p1.id), "name": "Alice", "seat_no": 1},
                {"id": str(self.p2.id), "name": "Bob", "seat_no": 2},
                {"id": str(self.p3.id), "name": "Charlie", "seat_no": 3},
                {"id": str(self.p4.id), "name": "David", "seat_no": 4},
            ]
        }

        results = []
        
        def run_sync(payload, client_instance):
            try:
                response = client_instance.post("/api/matches/sync/", payload, format="json")
                results.append(response)
            except Exception as e:
                results.append(e)

        client_a = APIClient()
        client_b = APIClient()

        t1 = threading.Thread(target=run_sync, args=(payload_a, client_a))
        t2 = threading.Thread(target=run_sync, args=(payload_b, client_b))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        success_count = 0
        locked_count = 0
        for res in results:
            if isinstance(res, Exception):
                self.fail(f"Sync raised exception: {res}")
            self.assertIn(res.status_code, [200, 207])
            if res.status_code == 200:
                success_count += 1
            elif res.status_code == 207:
                locked_count += 1
                self.assertEqual(len(res.data["errors"]), 1)
                self.assertIn("locked", res.data["errors"][0]["error"].lower())
        
        # At least one should succeed, and at most one should be locked
        self.assertTrue(success_count >= 1)
        self.assertTrue(locked_count <= 1)
            
        match = Match.objects.get(id=self.match_id)
        self.assertEqual(match.version, 2)
        self.assertIn(match.status, ["PLAYING", "MATCH_COMPLETE"])
