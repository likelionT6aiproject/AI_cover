import boto3
import os
import time
import uuid
import requests
from django.shortcuts import render
from django.http import JsonResponse
from pygame import mixer
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage

# Amazon Polly 및 Transcribe 클라이언트 생성
polly_client = boto3.client('polly', region_name='ap-northeast-2')
transcribe_client = boto3.client('transcribe', region_name='ap-northeast-2')

def text_to_speech(text, voice_id='Joanna'):
    response = polly_client.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId=voice_id
    )

    output_file = 'output.mp3'
    with open(output_file, 'wb') as file:
        file.write(response['AudioStream'].read())

    return output_file

@csrf_exempt
def speech_to_text(request):
    if request.method == 'POST' and request.FILES.get('audio_file'):
        audio_file = request.FILES['audio_file']
        file_name = str(uuid.uuid4()) + '.wav'
        file_path = default_storage.save(file_name, audio_file)

        input_bucket_name = 'jylion-bucket'
        output_bucket_name = 'jylion-bucket'

        job_name = str(uuid.uuid4())
        job_uri = f's3://{input_bucket_name}/{file_name}'

        # S3에 파일 업로드
        s3_client = boto3.client('s3', region_name='ap-northeast-2')
        s3_client.upload_file(file_path, input_bucket_name, file_name)

        # Transcribe 작업 시작
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode='en-US',
            Media={'MediaFileUri': job_uri},
            OutputBucketName=output_bucket_name
        )

        # Transcribe 작업 완료까지 대기
        while True:
            result = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            status = result['TranscriptionJob']['TranscriptionJobStatus']
            if status in ['COMPLETED', 'FAILED']:
                break
            time.sleep(5)

        if status == 'COMPLETED':
            transcript_file_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
            
            # 응답 상태 코드 및 본문 확인
            try:
                transcript_response = requests.get(transcript_file_uri)
                if transcript_response.status_code == 200:
                    transcript_data = transcript_response.json()
                    transcript = transcript_data['results']['transcripts'][0]['transcript']
                else:
                    return JsonResponse({'error': f'Failed to retrieve transcript with status code {transcript_response.status_code}'}, status=500)
            except requests.RequestException as e:
                return JsonResponse({'error': f'Request failed: {str(e)}'}, status=500)
            except ValueError as e:
                return JsonResponse({'error': f'Failed to decode JSON response: {str(e)}'}, status=500)
        else:
            return JsonResponse({'error': 'Transcription job failed.'}, status=500)

        # 임시 파일 삭제
        os.remove(file_path)

        return JsonResponse({'transcript': transcript})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def index(request):
    return render(request, 'index.html')

def tts(request):
    if request.method == 'POST':
        text = request.POST['text']
        voice_id = request.POST.get('voice_id', 'Joanna')

        output_file = text_to_speech(text, voice_id)

        # 음성 파일 재생
        mixer.init()
        mixer.music.load(output_file)
        mixer.music.play()

        while mixer.music.get_busy():
            time.sleep(1)

        mixer.quit()
        os.remove(output_file)

        return render(request, 'index.html', {'audio_file': output_file})
    return render(request, 'index.html')
