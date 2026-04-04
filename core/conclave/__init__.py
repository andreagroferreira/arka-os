"""The Conclave — Personal AI Advisory Board.

10 AI advisors personalized to the user's behavioral DNA:
- 5 Aligned: think like the user (amplify strengths)
- 5 Contrarian: opposite of the user (challenge biases)
Each advisor based on a real person with codified mental models.
"""

from core.conclave.schema import UserProfile, Advisor, ConclaveBoard
from core.conclave.matcher import match_advisors

__all__ = ["UserProfile", "Advisor", "ConclaveBoard", "match_advisors"]
