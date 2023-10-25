import unittest

from app import ProcessingPayload


class TestModels(unittest.TestCase):
    def test_from_input(self):
        input = {
            "steps": [
                {
                    "name": "step1",
                    "actions": [
                        {"action": "app1", "content": "content1"},
                        {"action": "app2", "content": "content2"},
                    ],
                },
                {
                    "name": "step2",
                    "actions": [
                        {"action": "app3", "content": "content3"},
                        {"action": "app4", "content": "content4"},
                    ],
                },
            ]
        }

        payload = ProcessingPayload.from_input(input)

        self.assertEqual(len(payload.steps), 2)

        self.assertEqual(payload.steps[0].name, "step1")
        self.assertEqual(len(payload.steps[0].actions), 2)
        self.assertEqual(payload.steps[0].actions[0].action, "app1")
        self.assertEqual(payload.steps[0].actions[0].content, "content1")
        self.assertEqual(payload.steps[0].actions[1].action, "app2")
        self.assertEqual(payload.steps[0].actions[1].content, "content2")

        self.assertEqual(payload.steps[1].name, "step2")
        self.assertEqual(len(payload.steps[1].actions), 2)
        self.assertEqual(payload.steps[1].actions[0].action, "app3")
        self.assertEqual(payload.steps[1].actions[0].content, "content3")
        self.assertEqual(payload.steps[1].actions[1].action, "app4")
        self.assertEqual(payload.steps[1].actions[1].content, "content4")


if __name__ == "__main__":
    unittest.main()
