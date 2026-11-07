// smtc_bridge.cpp
#pragma execution_character_set("utf-8")
#include <windows.h>
#include <systemmediatransportcontrolsinterop.h>
#include <windows.media.h>
#include <windows.storage.h>
#include <windows.storage.streams.h>
#include <wrl.h>
#include <roapi.h>
#include <shcore.h>
#include <shlwapi.h>
#include <vector>

#pragma comment(lib, "Shlwapi.lib")

using namespace Microsoft::WRL;
using namespace ABI::Windows::Media;
using namespace ABI::Windows::Foundation;
using namespace ABI::Windows::Storage;
using namespace ABI::Windows::Storage::Streams;

typedef void(__stdcall* CallbackFunc)();
CallbackFunc g_on_play_pause = nullptr;
CallbackFunc g_on_next = nullptr;
CallbackFunc g_on_prev = nullptr;

ComPtr<ISystemMediaTransportControls> g_smtc;
ComPtr<ISystemMediaTransportControls2> g_smtc2;
ComPtr<IRandomAccessStreamReference> g_current_thumbnail = nullptr;
EventRegistrationToken g_button_token;

using SMTCButtonEvent = ABI::Windows::Foundation::__FITypedEventHandler_2_Windows__CMedia__CSystemMediaTransportControls_Windows__CMedia__CSystemMediaTransportControlsButtonPressedEventArgs_t;

class ButtonPressedHandler : public RuntimeClass<RuntimeClassFlags<ClassicCom>, SMTCButtonEvent> {
public:
    HRESULT STDMETHODCALLTYPE Invoke(ISystemMediaTransportControls* sender, ISystemMediaTransportControlsButtonPressedEventArgs* args) override {
        SystemMediaTransportControlsButton button;
        args->get_Button(&button);
        if ((button == SystemMediaTransportControlsButton_Play || button == SystemMediaTransportControlsButton_Pause) && g_on_play_pause) {
            g_on_play_pause();
        }
        else if (button == SystemMediaTransportControlsButton_Next && g_on_next) {
            g_on_next();
        }
        else if (button == SystemMediaTransportControlsButton_Previous && g_on_prev) {
            g_on_prev();
        }
        return S_OK;
    }
};
ComPtr<ButtonPressedHandler> g_handler;

HSTRING MakeHString(const wchar_t* str) {
    HSTRING hstr = nullptr;
    if (str) WindowsCreateString(str, (UINT32)wcslen(str), &hstr);
    return hstr;
}

ComPtr<IRandomAccessStreamReference> CreateStreamFromFile(const wchar_t* filePath) {
    HANDLE hFile = CreateFileW(filePath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) return nullptr;

    DWORD fileSize = GetFileSize(hFile, NULL);
    if (fileSize == INVALID_FILE_SIZE) { CloseHandle(hFile); return nullptr; }

    std::vector<byte> buffer(fileSize);
    DWORD bytesRead = 0;
    ReadFile(hFile, buffer.data(), fileSize, &bytesRead, NULL);
    CloseHandle(hFile);

    ComPtr<IStream> stream;
    stream.Attach(SHCreateMemStream(buffer.data(), bytesRead));

    ComPtr<IRandomAccessStream> randomAccessStream;
    if (FAILED(CreateRandomAccessStreamOverStream(stream.Get(), BSOS_DEFAULT, IID_PPV_ARGS(&randomAccessStream)))) {
        return nullptr;
    }

    ComPtr<IRandomAccessStreamReferenceStatics> streamRefStatics;
    HSTRING classId = MakeHString(RuntimeClass_Windows_Storage_Streams_RandomAccessStreamReference);
    RoGetActivationFactory(classId, IID_PPV_ARGS(&streamRefStatics));
    WindowsDeleteString(classId);
    
    ComPtr<IRandomAccessStreamReference> streamRef;
    streamRefStatics->CreateFromStream(randomAccessStream.Get(), &streamRef);
    return streamRef;
}

extern "C" {
    __declspec(dllexport) bool __stdcall InitSMTC(HWND hwnd, CallbackFunc on_play_pause, CallbackFunc on_next, CallbackFunc on_prev) {
        RoInitialize(RO_INIT_MULTITHREADED);
        g_on_play_pause = on_play_pause;
        g_on_next = on_next;
        g_on_prev = on_prev;

        ComPtr<ISystemMediaTransportControlsInterop> interop;
        HSTRING classId = MakeHString(RuntimeClass_Windows_Media_SystemMediaTransportControls);

        HRESULT hr = RoGetActivationFactory(classId, IID_PPV_ARGS(&interop));
        WindowsDeleteString(classId);
        if (FAILED(hr)) return false;

        if (FAILED(interop->GetForWindow(hwnd, IID_PPV_ARGS(&g_smtc)))) return false;
        
        g_smtc.As(&g_smtc2);
        g_smtc->put_IsEnabled(true);
        g_smtc->put_IsPlayEnabled(true);
        g_smtc->put_IsPauseEnabled(true);
        g_smtc->put_IsNextEnabled(true);
        g_smtc->put_IsPreviousEnabled(true);
        g_smtc->put_IsStopEnabled(true);

        g_handler = Make<ButtonPressedHandler>();
        hr = g_smtc->add_ButtonPressed(g_handler.Get(), &g_button_token);
        return SUCCEEDED(hr);
    }

    __declspec(dllexport) void __stdcall UpdateMetadata(const wchar_t* title, const wchar_t* artist, const wchar_t* album, const wchar_t* cover_path) {
        if (!g_smtc) return;
        ComPtr<ISystemMediaTransportControlsDisplayUpdater> updater;
        if (SUCCEEDED(g_smtc->get_DisplayUpdater(&updater))) {
            updater->put_Type(MediaPlaybackType_Music);

            ComPtr<IMusicDisplayProperties> music_props;
            if (SUCCEEDED(updater->get_MusicProperties(&music_props))) {
                if (title) { HSTRING h = MakeHString(title); music_props->put_Title(h); WindowsDeleteString(h); }
                if (artist) { HSTRING h = MakeHString(artist); music_props->put_Artist(h); WindowsDeleteString(h); }

                if (album) {
                    ComPtr<IMusicDisplayProperties2> music_props2;
                    if (SUCCEEDED(music_props.As(&music_props2))) {
                        HSTRING h = MakeHString(album);
                        music_props2->put_AlbumTitle(h);
                        WindowsDeleteString(h);
                    }
                }
            }
            
            if (cover_path && wcslen(cover_path) > 0) {
                g_current_thumbnail = CreateStreamFromFile(cover_path);
            } else {
                g_current_thumbnail = nullptr;
            }

            updater->put_Thumbnail(g_current_thumbnail.Get());

            updater->Update();
        }
    }

    __declspec(dllexport) void __stdcall UpdatePlaybackStatus(int status) {
        if (!g_smtc) return;
        MediaPlaybackStatus s = MediaPlaybackStatus_Paused;
        if (status == 1) s = MediaPlaybackStatus_Playing;
        else if (status == 2) s = MediaPlaybackStatus_Stopped;
        g_smtc->put_PlaybackStatus(s);
    }

    __declspec(dllexport) void __stdcall UpdateTimeline(double current_sec, double total_sec) {
        if (!g_smtc2 || total_sec <= 0.0) return;

        ComPtr<ISystemMediaTransportControlsTimelineProperties> props;

        HSTRING classId = MakeHString(RuntimeClass_Windows_Media_SystemMediaTransportControlsTimelineProperties);
        HRESULT hr = RoGetActivationFactory(classId, IID_PPV_ARGS(&props));
        WindowsDeleteString(classId);

        if (FAILED(hr) || !props) return;

        TimeSpan start = {};
        TimeSpan end = {};
        TimeSpan position = {};

        end.Duration = (INT64)(total_sec * 10000000.0);
        position.Duration = (INT64)(current_sec * 10000000.0);

        props->put_StartTime(start);
        props->put_EndTime(end);
        props->put_Position(position);
        props->put_MinSeekTime(start);
        props->put_MaxSeekTime(end);

        g_smtc2->UpdateTimelineProperties(props.Get());
    }
}