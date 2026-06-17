from django.shortcuts import render

def home(request):

    context = {
        'active_page': 'home',
    }
    return render(request, 'core/home.html', context)