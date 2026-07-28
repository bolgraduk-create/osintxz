"""
Sentiment analyzer.

Responsible for emotional and
tone analysis of text data.

Architecture:

Text
 ↓
Token analysis
 ↓
Sentiment scoring
 ↓
Emotion detection
 ↓
Statistics
 ↓
Export
"""

from __future__ import annotations

from collections import Counter

from typing import Any


class SentimentAnalyzer:
    """
    Advanced sentiment analyzer.

    Initial implementation uses
    linguistic rules.

    Future:
        - ML models
        - transformers
        - LLM analysis
    """


    # ==========================================================
    # Lexicons
    # ==========================================================

    POSITIVE_WORDS = {
        "good",
        "great",
        "excellent",
        "love",
        "happy",
        "thanks",
        "nice",
        "perfect",
        "awesome",
        "success",
    }


    NEGATIVE_WORDS = {
        "bad",
        "terrible",
        "hate",
        "angry",
        "sad",
        "problem",
        "fail",
        "wrong",
        "danger",
        "conflict",
    }


    ANGER_WORDS = {
        "angry",
        "hate",
        "rage",
        "furious",
    }


    SADNESS_WORDS = {
        "sad",
        "sorry",
        "cry",
        "lost",
    }


    JOY_WORDS = {
        "happy",
        "love",
        "great",
        "awesome",
    }


    # ==========================================================
    # Main analysis
    # ==========================================================

    def analyze(
        self,
        text: str,
    ) -> dict[str, Any]:
        """
        Analyze single text.
        """


        tokens = self.tokenize(
            text
        )


        score = self.calculate_score(
            tokens
        )


        sentiment = (
            self.classify_sentiment(
                score
            )
        )


        emotions = (
            self.detect_emotions(
                tokens
            )
        )


        return {
            "text": text,
            "sentiment": sentiment,
            "score": score,
            "emotions": emotions,
            "confidence": (
                self.calculate_confidence(
                    tokens
                )
            ),
            "metadata": {},
        }


    # ==========================================================
    # Text processing
    # ==========================================================

    def tokenize(
        self,
        text: str,
    ) -> list[str]:

        return [
            word.lower()
            .strip(
                ".,!?;:\"'()[]{}"
            )
            for word in text.split()
        ]


    def calculate_score(
        self,
        tokens: list[str],
    ) -> float:

        positive = sum(
            1
            for token in tokens
            if token in self.POSITIVE_WORDS
        )


        negative = sum(
            1
            for token in tokens
            if token in self.NEGATIVE_WORDS
        )


        total = positive + negative


        if total == 0:
            return 0.0


        return round(
            (
                positive - negative
            )
            / total,
            3,
        )


    def classify_sentiment(
        self,
        score: float,
    ) -> str:

        if score > 0.2:
            return "positive"


        if score < -0.2:
            return "negative"


        return "neutral"


    def calculate_confidence(
        self,
        tokens: list[str],
    ) -> float:
        """
        Calculate confidence of sentiment analysis.

        Confidence grows with the amount
        of emotional indicators found.
        """

        emotional_words = (
            self.POSITIVE_WORDS
            |
            self.NEGATIVE_WORDS
        )


        matches = sum(
            1
            for token in tokens
            if token in emotional_words
        )


        if matches == 0:
            return 0.5


        confidence = min(
            0.5 + (matches * 0.1),
            0.95,
        )


        return round(
            confidence,
            2,
        )


    # ==========================================================
    # Emotion analysis
    # ==========================================================

    def detect_emotions(
        self,
        tokens: list[str],
    ) -> dict[str, float]:

        total = max(
            len(tokens),
            1,
        )


        return {

            "anger":
                self.count_words(
                    tokens,
                    self.ANGER_WORDS,
                )
                / total,


            "sadness":
                self.count_words(
                    tokens,
                    self.SADNESS_WORDS,
                )
                / total,


            "joy":
                self.count_words(
                    tokens,
                    self.JOY_WORDS,
                )
                / total,
        }


    def count_words(
        self,
        tokens: list[str],
        dictionary: set[str],
    ) -> int:

        return sum(
            1
            for token in tokens
            if token in dictionary
        )


    # ==========================================================
    # Conversation analysis
    # ==========================================================

    def analyze_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        results = []


        for message in messages:

            results.append(
                {
                    **message,
                    "analysis":
                        self.analyze(
                            message.get(
                                "text",
                                "",
                            )
                        ),
                }
            )


        return results


    def analyze_user_mood(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:

        scores = []


        for message in messages:

            result = self.analyze(
                message.get(
                    "text",
                    "",
                )
            )


            scores.append(
                result["score"]
            )


        return {

            "average_score":
                (
                    sum(scores)
                    /
                    len(scores)
                )
                if scores
                else 0,

            "messages":
                len(scores),
        }


    def mood_timeline(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        return [
            {
                "date":
                    message.get(
                        "date"
                    ),

                "score":
                    self.analyze(
                        message.get(
                            "text",
                            "",
                        )
                    )["score"],
            }
            for message in messages
        ]


    # ==========================================================
    # Conflict detection
    # ==========================================================

    def conflict_score(
        self,
        text: str,
    ) -> float:

        result = self.analyze(
            text
        )


        anger = result["emotions"]["anger"]

        negative = max(
            -result["score"],
            0,
        )


        return round(
            (
                anger + negative
            )
            / 2,
            3,
        )


    def detect_conflicts(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        conflicts = []


        for message in messages:

            score = self.conflict_score(
                message.get(
                    "text",
                    "",
                )
            )


            if score > 0.5:

                conflicts.append(
                    message
                )


        return conflicts


    # ==========================================================
    # Statistics
    # ==========================================================

    def build_statistics(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:

        sentiments = Counter(
            result["sentiment"]
            for result in results
        )


        return {
            "total": len(results),
            "sentiments": dict(sentiments),
        }


    # ==========================================================
    # Export
    # ==========================================================

    def export(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:

        return {
            "results": results,
            "statistics":
                self.build_statistics(
                    results
                ),
        }