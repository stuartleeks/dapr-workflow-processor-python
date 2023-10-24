import json
import unittest

from app import ProcessingAction, ProcessingPayload

class TestModels(unittest.TestCase):

    def test_from_input(self):
        input = [
                {
                    "action" : "app1",
                    "content" : "content1"
                },
                {
                    "action" : "app2",
                    "content" : "content2"
                }
            ]
        payload = ProcessingPayload.from_input(input)
        self.assertEqual(len(payload.actions), 2)
        
        self.assertEqual(payload.actions[0].action, "app1")
        self.assertEqual(payload.actions[0].content, "content1")

        self.assertEqual(payload.actions[1].action, "app2")
        self.assertEqual(payload.actions[1].content, "content2")

    def test_to_json(self):
        payload = ProcessingPayload([
            ProcessingAction("app1", "content1"),
            ProcessingAction("app2", "content2")
        ])

        json_result = payload.to_json()

        self.assertEqual(json_result, '{"actions": [{"action": "app1", "content": "content1"}, {"action": "app2", "content": "content2"}]}')

if __name__ == '__main__':
    unittest.main()