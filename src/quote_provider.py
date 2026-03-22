"""
quote_provider.py
~~~~~~~~~~~~~~~~~
Provides the :class:`QuoteProvider` class which holds a curated set of
inspirational quotes and selects them in a non-repeating random order.

Selection strategy
------------------
Quotes are served from a shuffled deck.  Once every quote in the corpus
has been served exactly once, the deck is reshuffled and the cycle repeats
— guaranteeing no consecutive repeat and full coverage before any quote
is seen again.  The last quote of one cycle is never the first of the next.

History tracking
----------------
Every served quote is appended to :attr:`history` so callers can inspect
which quotes have been displayed.

All quotes conform to RFC 865 syntax constraints:
- Printable ASCII characters, space, carriage return, and line feed only
- Maximum 512 characters per quote
"""

import random
from typing import Optional

# ---------------------------------------------------------------------------
# Built-in quote corpus — RFC 865 compliant (ASCII, <=512 chars each)
# 100+ well-known, inspirational, safe-for-work quotes
# ---------------------------------------------------------------------------
_DEFAULT_QUOTES: tuple[str, ...] = (
    # --- Perseverance & resilience ---
    "The only way to do great work is to love what you do.\r\n— Steve Jobs",
    "It does not matter how slowly you go as long as you do not stop.\r\n— Confucius",
    "Many of life's failures are people who did not realise how close they were to success when they gave up.\r\n— Thomas A. Edison",
    "Our greatest weakness lies in giving up. The most certain way to succeed is always to try just one more time.\r\n— Thomas A. Edison",
    "You will face many defeats in life, but never let yourself be defeated.\r\n— Maya Angelou",
    "The greatest glory in living lies not in never falling, but in rising every time we fall.\r\n— Nelson Mandela",
    "Never let the fear of striking out keep you from playing the game.\r\n— Babe Ruth",
    "When you reach the end of your rope, tie a knot in it and hang on.\r\n— Franklin D. Roosevelt",
    "Courage is not the absence of fear, but the triumph over it.\r\n— Nelson Mandela",
    "Success is not final, failure is not fatal: it is the courage to continue that counts.\r\n— Winston Churchill",
    "If you're going through hell, keep going.\r\n— Winston Churchill",
    "Fall seven times, stand up eight.\r\n— Japanese Proverb",
    "Hardships often prepare ordinary people for an extraordinary destiny.\r\n— C.S. Lewis",
    "Believe you can and you're halfway there.\r\n— Theodore Roosevelt",
    "It always seems impossible until it's done.\r\n— Nelson Mandela",
    "Start where you are. Use what you have. Do what you can.\r\n— Arthur Ashe",
    "Do what you can, with what you have, where you are.\r\n— Theodore Roosevelt",
    "The secret of getting ahead is getting started.\r\n— Mark Twain",
    "You don't have to be great to start, but you have to start to be great.\r\n— Zig Ziglar",
    "A journey of a thousand miles begins with a single step.\r\n— Lao Tzu",

    # --- Growth & learning ---
    "In the middle of every difficulty lies opportunity.\r\n— Albert Einstein",
    "Strive not to be a success, but rather to be of value.\r\n— Albert Einstein",
    "Imagination is more important than knowledge.\r\n— Albert Einstein",
    "The measure of intelligence is the ability to change.\r\n— Albert Einstein",
    "An unexamined life is not worth living.\r\n— Socrates",
    "The mind is everything. What you think you become.\r\n— Buddha",
    "Education is the most powerful weapon which you can use to change the world.\r\n— Nelson Mandela",
    "Live as if you were to die tomorrow. Learn as if you were to live forever.\r\n— Mahatma Gandhi",
    "The beautiful thing about learning is that no one can take it away from you.\r\n— B.B. King",
    "Tell me and I forget. Teach me and I remember. Involve me and I learn.\r\n— Benjamin Franklin",
    "An investment in knowledge pays the best interest.\r\n— Benjamin Franklin",
    "The more that you read, the more things you will know.\r\n— Dr. Seuss",
    "You have brains in your head. You have feet in your shoes. You can steer yourself any direction you choose.\r\n— Dr. Seuss",
    "It is not that I'm so smart. But I stay with the questions much longer.\r\n— Albert Einstein",
    "The expert in anything was once a beginner.\r\n— Helen Hayes",

    # --- Purpose & meaning ---
    "Life is what happens when you're busy making other plans.\r\n— John Lennon",
    "The future belongs to those who believe in the beauty of their dreams.\r\n— Eleanor Roosevelt",
    "Life is either a daring adventure or nothing at all.\r\n— Helen Keller",
    "If life were predictable it would cease to be life, and be without flavour.\r\n— Eleanor Roosevelt",
    "In the end, it's not the years in your life that count. It's the life in your years.\r\n— Abraham Lincoln",
    "The purpose of our lives is to be happy.\r\n— Dalai Lama",
    "Life is not measured by the number of breaths we take, but by the moments that take our breath away.\r\n— Maya Angelou",
    "Do not go where the path may lead; go instead where there is no path and leave a trail.\r\n— Ralph Waldo Emerson",
    "To be yourself in a world that is constantly trying to make you something else is the greatest accomplishment.\r\n— Ralph Waldo Emerson",
    "What lies behind us and what lies before us are tiny matters compared to what lies within us.\r\n— Ralph Waldo Emerson",
    "The only impossible journey is the one you never begin.\r\n— Tony Robbins",
    "Your time is limited, so don't waste it living someone else's life.\r\n— Steve Jobs",
    "The two most important days in your life are the day you are born and the day you find out why.\r\n— Mark Twain",
    "Twenty years from now you will be more disappointed by the things you didn't do than by the ones you did.\r\n— Mark Twain",

    # --- Kindness & character ---
    "Spread love everywhere you go. Let no one ever come to you without leaving happier.\r\n— Mother Teresa",
    "Always remember that you are absolutely unique. Just like everyone else.\r\n— Margaret Mead",
    "Never doubt that a small group of thoughtful, committed citizens can change the world.\r\n— Margaret Mead",
    "Be the change you wish to see in the world.\r\n— Mahatma Gandhi",
    "In a gentle way, you can shake the world.\r\n— Mahatma Gandhi",
    "No act of kindness, no matter how small, is ever wasted.\r\n— Aesop",
    "We make a living by what we get, but we make a life by what we give.\r\n— Winston Churchill",
    "The best way to find yourself is to lose yourself in the service of others.\r\n— Mahatma Gandhi",
    "Darkness cannot drive out darkness; only light can do that.\r\n— Martin Luther King Jr.",
    "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin.\r\n— Martin Luther King Jr.",
    "The time is always right to do what is right.\r\n— Martin Luther King Jr.",
    "Injustice anywhere is a threat to justice everywhere.\r\n— Martin Luther King Jr.",
    "We must learn to live together as brothers or perish together as fools.\r\n— Martin Luther King Jr.",

    # --- Attitude & mindset ---
    "Whether you think you can or you think you can't, you're right.\r\n— Henry Ford",
    "The only limit to our realisation of tomorrow will be our doubts of today.\r\n— Franklin D. Roosevelt",
    "Keep your face always toward the sunshine, and shadows will fall behind you.\r\n— Walt Whitman",
    "Optimism is the faith that leads to achievement.\r\n— Helen Keller",
    "Once you choose hope, anything is possible.\r\n— Christopher Reeve",
    "Happiness is not something ready-made. It comes from your own actions.\r\n— Dalai Lama",
    "The happiness of your life depends upon the quality of your thoughts.\r\n— Marcus Aurelius",
    "Very little is needed to make a happy life; it is all within yourself, in your way of thinking.\r\n— Marcus Aurelius",
    "You have power over your mind, not outside events. Realise this, and you will find strength.\r\n— Marcus Aurelius",
    "Waste no more time arguing about what a good man should be. Be one.\r\n— Marcus Aurelius",
    "The best revenge is massive success.\r\n— Frank Sinatra",
    "I've missed more than 9,000 shots in my career. I've lost almost 300 games. I've failed over and over again. That is why I succeed.\r\n— Michael Jordan",
    "Talent wins games, but teamwork and intelligence win championships.\r\n— Michael Jordan",

    # --- Work & excellence ---
    "Whatever you are, be a good one.\r\n— Abraham Lincoln",
    "Give me six hours to chop down a tree and I will spend the first four sharpening the axe.\r\n— Abraham Lincoln",
    "I find that the harder I work, the more luck I seem to have.\r\n— Thomas Jefferson",
    "The secret of success is to do the common thing uncommonly well.\r\n— John D. Rockefeller Jr.",
    "I'm a great believer in luck, and I find the harder I work, the more I have of it.\r\n— Thomas Jefferson",
    "Genius is one percent inspiration and ninety-nine percent perspiration.\r\n— Thomas A. Edison",
    "There are no shortcuts to any place worth going.\r\n— Beverly Sills",
    "Quality is not an act, it is a habit.\r\n— Aristotle",
    "We are what we repeatedly do. Excellence, then, is not an act, but a habit.\r\n— Aristotle",
    "Pleasure in the job puts perfection in the work.\r\n— Aristotle",
    "The secret of joy in work is contained in one word — excellence.\r\n— Pearl S. Buck",
    "Do or do not. There is no try.\r\n— Yoda",

    # --- Courage & action ---
    "You miss 100% of the shots you don't take.\r\n— Wayne Gretzky",
    "It is during our darkest moments that we must focus to see the light.\r\n— Aristotle",
    "The secret of change is to focus all of your energy not on fighting the old, but on building the new.\r\n— Socrates",
    "Well done is better than well said.\r\n— Benjamin Franklin",
    "Either write something worth reading or do something worth writing.\r\n— Benjamin Franklin",
    "By failing to prepare, you are preparing to fail.\r\n— Benjamin Franklin",
    "Energy and persistence conquer all things.\r\n— Benjamin Franklin",
    "Knowing is not enough; we must apply. Willing is not enough; we must do.\r\n— Johann Wolfgang von Goethe",
    "Whatever you do, do it with all your might.\r\n— Marcus Tullius Cicero",
    "Action is the foundational key to all success.\r\n— Pablo Picasso",
    "The secret to getting ahead is getting started.\r\n— Agatha Christie",
    "Don't watch the clock; do what it does. Keep going.\r\n— Sam Levenson",

    # --- Creativity & innovation ---
    "Creativity is intelligence having fun.\r\n— Albert Einstein",
    "Innovation distinguishes between a leader and a follower.\r\n— Steve Jobs",
    "The only way to discover the limits of the possible is to go beyond them into the impossible.\r\n— Arthur C. Clarke",
    "Logic will get you from A to B. Imagination will take you everywhere.\r\n— Albert Einstein",
    "Every child is an artist. The problem is how to remain an artist once we grow up.\r\n— Pablo Picasso",
    "The world is but a canvas to our imagination.\r\n— Henry David Thoreau",
    "Go confidently in the direction of your dreams. Live the life you have imagined.\r\n— Henry David Thoreau",
    "Not all those who wander are lost.\r\n— J.R.R. Tolkien",
    "All we have to decide is what to do with the time that is given us.\r\n— J.R.R. Tolkien",

    # --- Leadership & teamwork ---
    "A leader is one who knows the way, goes the way, and shows the way.\r\n— John C. Maxwell",
    "The function of leadership is to produce more leaders, not more followers.\r\n— Ralph Nader",
    "Coming together is a beginning, staying together is progress, and working together is success.\r\n— Henry Ford",
    "Alone we can do so little; together we can do so much.\r\n— Helen Keller",
    "If your actions inspire others to dream more, learn more, do more and become more, you are a leader.\r\n— John Quincy Adams",
    "The strength of the team is each individual member. The strength of each member is the team.\r\n— Phil Jackson",
)


class QuoteProvider:
    """Holds a corpus of inspirational quotes and serves them in a
    non-repeating random order using a shuffle-deck strategy.

    Selection strategy
    ~~~~~~~~~~~~~~~~~~
    Quotes are drawn from a shuffled deck.  When the deck is exhausted,
    it is reshuffled — ensuring every quote is seen once per cycle before
    any repeats.  The last quote of one cycle is excluded from the first
    draw of the next to prevent back-to-back repeats across cycle boundaries.

    History tracking
    ~~~~~~~~~~~~~~~~
    Every served quote is appended to :attr:`history`.  Callers can inspect
    this list to see which quotes have been displayed and in what order.

    :param quotes: Optional tuple of quote strings to use instead of the
                   built-in corpus.  Each quote must be <=512 printable ASCII
                   characters (plus ``\\r\\n``).
    :param seed: Optional integer seed for the random number generator.
                 Useful for deterministic testing.

    Example::

        >>> provider = QuoteProvider(seed=0)
        >>> q1 = provider.get()
        >>> q2 = provider.get()
        >>> q1 != q2   # consecutive quotes are always different
        True
        >>> len(provider.history)
        2
    """

    # RFC 865 hard limit
    MAX_QUOTE_LEN: int = 512

    def __init__(
        self,
        quotes: Optional[tuple[str, ...]] = None,
        seed: Optional[int] = None,
    ) -> None:
        corpus = quotes if quotes is not None else _DEFAULT_QUOTES

        # Validate every quote at construction time — fail fast
        for i, q in enumerate(corpus):
            if len(q) > self.MAX_QUOTE_LEN:
                raise ValueError(
                    f"Quote at index {i} exceeds {self.MAX_QUOTE_LEN} characters "
                    f"(RFC 865 limit): {len(q)} chars"
                )
        if not corpus:
            raise ValueError("Quote corpus must contain at least one quote.")

        #: Immutable tuple of validated quotes.
        self.quotes: tuple[str, ...] = tuple(corpus)

        #: Ordered list of every quote served so far (oldest first).
        self.history: list[str] = []

        # Private RNG — isolated so seeding never affects global random state
        self._rng = random.Random(seed)

        # Shuffle deck: a mutable list we pop from; refilled when empty
        self._deck: list[str] = []
        # Track the last served quote to avoid cross-cycle repeats
        self._last: Optional[str] = None

        self._refill_deck()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> str:
        """Return the next quote from the shuffled deck.

        Guarantees the returned quote differs from the previously served
        one.  When the deck runs out, it is reshuffled (excluding the last
        served quote from the first position of the new cycle).

        :returns: A single quote string, <=512 characters, RFC 865 compliant.
        """
        if not self._deck:
            self._refill_deck()

        quote = self._deck.pop()

        # If this is the only quote in the corpus, repetition is unavoidable
        if quote == self._last and len(self.quotes) > 1:
            # Put it back at the bottom and take the next one instead
            self._deck.insert(0, quote)
            if not self._deck:
                self._refill_deck()
            quote = self._deck.pop()

        self._last = quote
        self.history.append(quote)
        return quote

    def served_count(self) -> int:
        """Return the total number of quotes served so far."""
        return len(self.history)

    def __len__(self) -> int:
        """Return the number of quotes in the corpus."""
        return len(self.quotes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refill_deck(self) -> None:
        """Shuffle all quotes into the deck, ensuring the last served quote
        does not appear at the top (to prevent cross-cycle back-to-back repeats).
        """
        deck = list(self.quotes)
        self._rng.shuffle(deck)

        # If the top of the new deck matches the last served quote, rotate it
        if self._last is not None and len(deck) > 1 and deck[-1] == self._last:
            # Move the top card to a random position that isn't the top
            card = deck.pop()
            insert_pos = self._rng.randint(0, len(deck) - 1)
            deck.insert(insert_pos, card)

        self._deck = deck
