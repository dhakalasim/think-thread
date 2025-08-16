from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


# ----------------------------
# Core hospital directory
# ----------------------------
class Hospital(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    code = models.SlugField(max_length=64, unique=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("hospital", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} – {self.hospital.name}"


class Doctor(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ON_LEAVE = "on_leave", "On Leave"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="doctors")
    departments = models.ManyToManyField(Department, related_name="doctors", blank=True)
    full_name = models.CharField(max_length=150, db_index=True)
    designation = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


# ----------------------------
# Patients & appointments
# ----------------------------
class Patient(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        UNSPECIFIED = "unspecified", "Unspecified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="patients")
    full_name = models.CharField(max_length=150)
    gender = models.CharField(max_length=16, choices=Gender.choices, default=Gender.UNSPECIFIED)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    external_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="ID from EHR/HIS if synchronized",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "phone"]),
            models.Index(fields=["hospital", "email"]),
            models.Index(fields=["external_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name


class DoctorAvailability(models.Model):
    """
    Defines bookable time windows for a doctor (e.g., Mon 09:00–12:00).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="availabilities")
    weekday = models.PositiveSmallIntegerField(
        help_text="0=Monday ... 6=Sunday"
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=1, help_text="Max concurrent bookings")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("doctor", "weekday", "start_time", "end_time")
        ordering = ["doctor__full_name", "weekday", "start_time"]

    def __str__(self):
        return f"{self.doctor} {self.weekday} {self.start_time}-{self.end_time}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No-show"

    class Source(models.TextChoices):
        CHATBOT = "chatbot", "Chatbot"
        MANUAL = "manual", "Manual"
        CALL_CENTER = "call_center", "Call Center"
        PORTAL = "portal", "Patient Portal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="appointments")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments"
    )

    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.CHATBOT)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "start_at"]),
            models.Index(fields=["doctor", "start_at"]),
            models.Index(fields=["patient", "start_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_at__gt=models.F("start_at")),
                name="appointment_end_after_start",
            )
        ]
        ordering = ["-start_at"]

    def __str__(self):
        return f"{self.patient} ↔ {self.doctor} @ {self.start_at:%Y-%m-%d %H:%M}"


# ----------------------------
# NLP configuration
# ----------------------------
class Intent(models.Model):
    """
    Examples: 'book_appointment', 'cancel_appointment', 'faq_symptoms', 'greeting'
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    training_phrases = models.JSONField(default=list, blank=True)
    responses = models.JSONField(default=list, blank=True, help_text="Default templated responses")

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.name


class Entity(models.Model):
    """
    Generic entities extracted from utterances (e.g., date, symptom, doctor_name).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    synonyms = models.JSONField(default=list, blank=True)
    regex = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class NLPModelVersion(models.Model):
    """
    Track deployed NLP/LLM configurations (useful for A/B & auditability).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=120, help_text="e.g., OpenAI, Anthropic, Local")
    model_id = models.CharField(max_length=120, help_text="e.g., gpt-4o-mini, custom-transformer-xx")
    parameters = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False)
    deployed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-deployed_at", "name"]

    def __str__(self):
        return f"{self.provider}:{self.model_id}"


# ----------------------------
# Knowledge & FAQs
# ----------------------------
class FAQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=300, db_index=True)
    answer = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True)

    is_published = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("hospital", "question")
        ordering = ["question"]

    def __str__(self):
        return self.question


class KnowledgeBaseArticle(models.Model):
    """
    Longer health info pages (e.g., “What to do for a fever?”), optionally chunked for retrieval.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="kb_articles")
    title = models.CharField(max_length=200, db_index=True)
    body = models.TextField()
    topics = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    embedding = models.JSONField(default=list, blank=True, help_text="Vector embedding if used")

    is_published = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


# ----------------------------
# Real-time data integrations
# ----------------------------
class RealTimeDataSource(models.Model):
    """
    Configure endpoints for real-time info (e.g., bed availability, lab queue, token system).
    """
    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        DOWN = "down", "Down"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="data_sources")
    name = models.CharField(max_length=150)
    key = models.SlugField(max_length=64, unique=True)
    base_url = models.URLField()
    auth = models.JSONField(default=dict, blank=True, help_text="Headers/tokens if required")
    mapping = models.JSONField(default=dict, blank=True, help_text="Field mapping for normalization")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.HEALTHY)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("hospital", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.hospital.name})"


class RealTimeSnapshot(models.Model):
    """
    Stores latest normalized payloads from data sources (for quick serving & audit).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(RealTimeDataSource, on_delete=models.CASCADE, related_name="snapshots")
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.source.key} @ {self.captured_at.isoformat()}"


# ----------------------------
# Chat sessions & messages
# ----------------------------
class ChatSession(models.Model):
    class Channel(models.TextChoices):
        WEB = "web", "Web"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        MESSENGER = "messenger", "Messenger"
        KIOSK = "kiosk", "Kiosk"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="chat_sessions")
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions")
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.WEB)
    active_model = models.ForeignKey(
        NLPModelVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions"
    )
    locale = models.CharField(max_length=16, default="en", help_text="e.g., en, ne")

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        who = self.patient.full_name if self.patient else "Guest"
        return f"Session {self.pk} – {who}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        BOT = "bot", "Bot"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True, help_text="Rich content/cards/buttons")
    intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True)
    entities = models.JSONField(default=dict, blank=True)

    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    latency_ms = models.PositiveIntegerField(default=0, help_text="LLM/processing latency")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["intent"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.text[:60]}"


# ----------------------------
# Booking pipeline (via chatbot)
# ----------------------------
class BookingRequest(models.Model):
    """
    Temporary booking state captured via conversational slots before creating Appointment.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(ChatSession, on_delete=models.CASCADE, related_name="booking_request")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    slots = models.JSONField(default=dict, blank=True, help_text="Collected slots: date, time, symptom, etc.")
    is_ready = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking draft for session {self.session_id}"


# ----------------------------
# Governance, feedback, audit
# ----------------------------
class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="feedback")
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback")
    rating = models.IntegerField(
        default=0,
        help_text="e.g., -1 (thumbs down), 0 (neutral), 1 (thumbs up) or a 1–5 scale",
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    """
    Records sensitive actions (PHI reads, appointment creation/cancellation, admin changes).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["hospital", "created_at"])]


# ----------------------------
# Admin / configuration
# ----------------------------
class BotSetting(models.Model):
    """
    Global per-hospital bot settings (greeting, handoff thresholds, guardrails).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.OneToOneField(Hospital, on_delete=models.CASCADE, related_name="bot_setting")
    greeting_message = models.TextField(default="Hi! I can help with FAQs and appointments.")
    fallback_message = models.TextField(default="Sorry, I didn’t catch that. Can you rephrase?")
    human_handoff_threshold = models.PositiveSmallIntegerField(
        default=2, help_text="Escalate after N fallbacks"
    )
    allowed_locales = models.JSONField(default=list, blank=True)
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="e.g., {'mon': ['09:00-17:00'], 'sat': []}",
    )
    escalation_contacts = models.JSONField(default=list, blank=True, help_text="On-call staff info")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BotSetting({self.hospital.name})"
