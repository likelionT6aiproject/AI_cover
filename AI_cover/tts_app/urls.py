from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('tts/', views.tts, name='text_to_speech'),
    path('stt/', views.speech_to_text, name='speech_to_text'),
]
