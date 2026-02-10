// AccelByte login/register panel - implementation

// AB_MCP_BEGIN:AccelByte.Login.Panel
// {
//   "service": "auth",
//   "provider": "accelbyte",
//   "language": "unreal-cpp",
//   "description": "Self-contained Unreal Slate UI panel for AccelByte authentication: username/password login, account registration (device ID then headless upgrade), and logout. Covers auth, user identity, account creation, login, logout, credentials (username, password), sign-in, sign-out.",
//   "keywords": ["login", "auth", "authentication", "account", "username", "password", "user", "identity", "credentials", "register", "logout", "sign-in", "sign-out", "headless", "upgrade"],
//   "controllerClass": "FAccelByteLoginPanel",
//   "uiWidgetClass": "SAccelByteLoginWidget",
//   "stateEnum": "ELoginPanelState",
//   "publicInterface": {
//     "initialise": "void Initialise()",
//     "show": "void Show(float Width = 400.f, float Height = 380.f)",
//     "hide": "void Hide()",
//     "buildWidget": "TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 380.f)",
//     "onLoginClicked": "void OnLoginClicked(const FString& Username, const FString& Password)",
//     "onRegisterClicked": "void OnRegisterClicked(const FString& Username, const FString& Password, const FString& DisplayName)",
//     "onLogoutClicked": "void OnLogoutClicked()"
//   },
//   "asyncState": {
//     "stateField": "State",
//     "registerPendingFlag": "bRegisterPending",
//     "pendingRegisterUsernameField": "PendingRegisterUsername",
//     "pendingRegisterPasswordField": "PendingRegisterPassword"
//   },
//   "moduleDependencies": ["Slate", "SlateCore", "OnlineSubsystem"],
//   "integrationHints": ["Install the AccelByte Unreal SDK first (use the install_unreal_sdk tool) if not already installed. Then add these to PublicDependencyModuleNames in your module's .Build.cs: Slate, SlateCore, OnlineSubsystem (for identity/login), and your AccelByte SDK module."]
// }
// AB_MCP_END:AccelByte.Login.Panel

// AccelByte login/register panel - implementation

#include "AccelByteLoginPanel.h"
#include "Async/Async.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/OnlineIdentityInterface.h"
#include "OnlineSubsystemAccelByte.h"
#include "OnlineIdentityInterfaceAccelByte.h"
#include "InterfaceModels/OnlineIdentityInterfaceAccelByteModels.h"
#include "Core/AccelByteUtilities.h"
#include "Core/AccelByteApiClient.h"
#include "Core/AccelByteError.h"
#include "Api/AccelByteUserApi.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Layout/SSpacer.h"

using namespace AccelByte;
using namespace AccelByte::Api;

namespace
{
	const float LoginPanelEditBoxHeight = 44.f;
	const int32 LoginPanelTitleFontSize = 44;
	const int32 LoginPanelBodyFontSize = 22;
	const int32 LoginPanelButtonFontSize = 22;
}

void FAccelByteLoginPanel::Initialise()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteLoginPanel::Initialise - No OnlineSubsystem"));
		State = ELoginPanelState::LoggedOut;
		ErrorText.Empty();
		bRegisterMode = false;
		return;
	}
	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteLoginPanel::Initialise - No Identity interface"));
		State = ELoginPanelState::LoggedOut;
		ErrorText.Empty();
		bRegisterMode = false;
		return;
	}
	State = (Identity->GetLoginStatus(0) == ELoginStatus::LoggedIn) ? ELoginPanelState::LoggedIn : ELoginPanelState::LoggedOut;
	ErrorText.Empty();
	bRegisterMode = false;
	bRegisterPending = false;
	PendingRegisterUsername.Empty();
	PendingRegisterPassword.Empty();
}

FAccelByteLoginPanel::~FAccelByteLoginPanel()
{
	// Critical: Unbind all delegates before destruction to prevent dangling pointer callbacks
	UnbindLoginDelegate();
	UnbindLogoutDelegate();
	
	// Hide and clear widget to ensure proper cleanup
	if (bVisible)
	{
		Hide();
	}
	Widget.Reset();
	RootWidget.Reset();
}

void FAccelByteLoginPanel::Show(float Width, float Height)
{
	if (bVisible)
	{
		return;
	}
	if (!GEngine || !GEngine->GameViewport)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteLoginPanel::Show - No GameViewport available"));
		return;
	}
	EnsureWidgetCreated(Width, Height);
	if (!Widget.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteLoginPanel::Show - Widget creation failed"));
		return;
	}
	RootWidget = Widget;
	GEngine->GameViewport->AddViewportWidgetContent(Widget.ToSharedRef());
	bVisible = true;
	RefreshWidget();

	// Use GameAndUI so the L key toggle still works while panel is visible
	UWorld* World = GEngine->GameViewport ? GEngine->GameViewport->GetWorld() : nullptr;
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	if (PC)
	{
		FInputModeGameAndUI InputMode;
		InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
		InputMode.SetHideCursorDuringCapture(false);
		PC->SetInputMode(InputMode);
	}
	if (Widget.IsValid())
	{
		Widget->RequestFocusOnFirstEdit();
	}
}

void FAccelByteLoginPanel::Hide()
{
	if (!bVisible)
	{
		return;
	}
	if (GEngine && GEngine->GameViewport && Widget.IsValid())
	{
		GEngine->GameViewport->RemoveViewportWidgetContent(Widget.ToSharedRef());
	}
	// Restore game input so viewport gets keys again
	UWorld* World = GEngine && GEngine->GameViewport ? GEngine->GameViewport->GetWorld() : nullptr;
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	if (PC)
	{
		FInputModeGameOnly InputMode;
		PC->SetInputMode(InputMode);
	}
	bVisible = false;
}

TSharedPtr<SWidget> FAccelByteLoginPanel::GetWidget() const
{
	return Widget;
}

TSharedRef<SWidget> FAccelByteLoginPanel::BuildWidget(float Width, float Height)
{
	EnsureWidgetCreated(Width, Height);
	check(Widget.IsValid());
	return Widget.ToSharedRef();
}

void FAccelByteLoginPanel::OnLoginClicked(const FString& Username, const FString& Password)
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}
	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity not available"));
		return;
	}
	UnbindLoginDelegate();
	SetError(FString());
	SetState(ELoginPanelState::LoggingIn);
	bRegisterPending = false;
	RefreshWidget();

	FOnlineAccountCredentialsAccelByte Creds(EAccelByteLoginType::AccelByte, Username, Password);
	LoginCompleteHandle = Identity->AddOnLoginCompleteDelegate_Handle(0, FOnLoginCompleteDelegate::CreateSP(this, &FAccelByteLoginPanel::OnLoginComplete));
	Identity->Login(0, Creds);
}

void FAccelByteLoginPanel::OnDeviceIdLoginClicked()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}
	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity not available"));
		return;
	}
	UnbindLoginDelegate();
	SetError(FString());
	SetState(ELoginPanelState::LoggingIn);
	bRegisterPending = false;  // CRITICAL: No upgrade needed for device ID login
	RefreshWidget();

	// Device ID login - no username/password required
	FOnlineAccountCredentialsAccelByte Creds(EAccelByteLoginType::DeviceId, TEXT(""), TEXT(""));
	LoginCompleteHandle = Identity->AddOnLoginCompleteDelegate_Handle(0, FOnLoginCompleteDelegate::CreateSP(this, &FAccelByteLoginPanel::OnLoginComplete));
	Identity->Login(0, Creds);
}

void FAccelByteLoginPanel::OnLoginComplete(int32 LocalUserNum, bool bWasSuccessful, const FUniqueNetId& UserId, const FString& Error)
{
	UnbindLoginDelegate();
	if (bRegisterPending)
	{
		if (!bWasSuccessful)
		{
			AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak(), Error]()
			{
				if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
				{
					StrongThis->bRegisterPending = false;
					StrongThis->PendingRegisterUsername.Empty();
					StrongThis->PendingRegisterPassword.Empty();
					StrongThis->SetState(ELoginPanelState::LoggedOut);
					StrongThis->SetError(Error.IsEmpty() ? TEXT("Could not create account.") : Error);
					StrongThis->RefreshWidget();
				}
			});
			return;
		}
		FOnlineSubsystemAccelByte* ABSubsystem = static_cast<FOnlineSubsystemAccelByte*>(IOnlineSubsystem::Get());
		if (!ABSubsystem)
		{
			AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
			{
				if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
				{
					StrongThis->bRegisterPending = false;
					StrongThis->PendingRegisterUsername.Empty();
					StrongThis->PendingRegisterPassword.Empty();
					StrongThis->SetState(ELoginPanelState::LoggedOut);
					StrongThis->SetError(TEXT("AccelByte subsystem not available."));
					StrongThis->RefreshWidget();
				}
			});
			return;
		}
		AccelByte::FApiClientPtr ApiClient = ABSubsystem->GetApiClient(LocalUserNum);
		if (!ApiClient.IsValid())
		{
			auto Instance = ABSubsystem->GetAccelByteInstance().Pin();
			if (Instance.IsValid())
			{
				ApiClient = Instance->GetApiClient(FString::Printf(TEXT("%d"), LocalUserNum));
			}
		}
		if (!ApiClient.IsValid())
		{
			AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
			{
				if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
				{
					StrongThis->bRegisterPending = false;
					StrongThis->PendingRegisterUsername.Empty();
					StrongThis->PendingRegisterPassword.Empty();
					StrongThis->SetState(ELoginPanelState::LoggedOut);
					StrongThis->SetError(TEXT("Could not get API client for upgrade."));
					StrongThis->RefreshWidget();
				}
			});
			return;
		}
		Api::UserPtr UserApi = ApiClient->GetUserApi().Pin();
		if (!UserApi.IsValid())
		{
			AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
			{
				if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
				{
					StrongThis->bRegisterPending = false;
					StrongThis->PendingRegisterUsername.Empty();
					StrongThis->PendingRegisterPassword.Empty();
					StrongThis->SetState(ELoginPanelState::LoggedOut);
					StrongThis->SetError(TEXT("User API not available."));
					StrongThis->RefreshWidget();
				}
			});
			return;
		}
		FString User = PendingRegisterUsername;
		FString Pass = PendingRegisterPassword;
		THandler<FAccountUserData> OnUpgradeSuccessHandler = THandler<FAccountUserData>::CreateSP(this, &FAccelByteLoginPanel::OnUpgradeSuccess);
		FErrorHandler OnUpgradeErrorHandler = FErrorHandler::CreateSP(this, &FAccelByteLoginPanel::OnUpgradeError);
		UserApi->Upgrade(User, Pass, OnUpgradeSuccessHandler, OnUpgradeErrorHandler);
		return;
	}
	AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak(), bWasSuccessful, Error]()
	{
		if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
		{
			if (bWasSuccessful)
			{
				StrongThis->SetState(ELoginPanelState::LoggedIn);
				StrongThis->SetError(FString());
			}
			else
			{
				StrongThis->SetState(ELoginPanelState::LoggedOut);
				StrongThis->SetError(Error.IsEmpty() ? TEXT("Login failed.") : Error);
			}
			StrongThis->RefreshWidget();
		}
	});
}

void FAccelByteLoginPanel::OnLogoutClicked()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetState(ELoginPanelState::LoggedOut);
		RefreshWidget();
		return;
	}
	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetState(ELoginPanelState::LoggedOut);
		RefreshWidget();
		return;
	}
	UnbindLogoutDelegate();
	SetState(ELoginPanelState::LoggingOut);
	RefreshWidget();

	FOnlineIdentityAccelByte* ABIdentity = static_cast<FOnlineIdentityAccelByte*>(Identity.Get());
	if (ABIdentity)
	{
		LogoutCompleteHandle = ABIdentity->AddAccelByteOnLogoutCompleteDelegate_Handle(0, FAccelByteOnLogoutCompleteDelegate::CreateSP(this, &FAccelByteLoginPanel::OnLogoutComplete));
	}
	Identity->Logout(0);
	if (!ABIdentity)
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
		{
			if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
			{
				StrongThis->SetState(ELoginPanelState::LoggedOut);
				StrongThis->RefreshWidget();
			}
		});
	}
}

void FAccelByteLoginPanel::OnLogoutComplete(int32 LocalUserNum, bool bWasSuccessful, const FOnlineErrorAccelByte& Error)
{
	UnbindLogoutDelegate();
	AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
	{
		if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
		{
			StrongThis->SetState(ELoginPanelState::LoggedOut);
			StrongThis->SetError(FString());
			StrongThis->ClearStoredCredentials();
			StrongThis->RefreshWidget();
		}
	});
}

void FAccelByteLoginPanel::UnbindLoginDelegate()
{
	if (LoginCompleteHandle.IsValid())
	{
		IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
		if (OSS)
		{
			IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
			if (Identity.IsValid())
			{
				Identity->ClearOnLoginCompleteDelegate_Handle(0, LoginCompleteHandle);
			}
		}
		LoginCompleteHandle.Reset();
	}
}

void FAccelByteLoginPanel::UnbindLogoutDelegate()
{
	if (LogoutCompleteHandle.IsValid())
	{
		IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
		if (OSS)
		{
			IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
			FOnlineIdentityAccelByte* ABIdentity = Identity.IsValid() ? static_cast<FOnlineIdentityAccelByte*>(Identity.Get()) : nullptr;
			if (ABIdentity)
			{
				ABIdentity->ClearAccelByteOnLogoutCompleteDelegate_Handle(0, LogoutCompleteHandle);
			}
		}
		LogoutCompleteHandle.Reset();
	}
}

void FAccelByteLoginPanel::OnRegisterClicked(const FString& Username, const FString& Password, const FString& DisplayName)
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		RefreshWidget();
		return;
	}
	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity not available"));
		RefreshWidget();
		return;
	}
	PendingRegisterUsername = Username;
	PendingRegisterPassword = Password;
	bRegisterPending = true;
	SetError(FString());
	SetState(ELoginPanelState::LoggingIn);
	RefreshWidget();

	UnbindLoginDelegate();
	FOnlineAccountCredentialsAccelByte Creds(EAccelByteLoginType::DeviceId, TEXT(""), TEXT(""), true);
	LoginCompleteHandle = Identity->AddOnLoginCompleteDelegate_Handle(0, FOnLoginCompleteDelegate::CreateSP(this, &FAccelByteLoginPanel::OnLoginComplete));
	Identity->Login(0, Creds);
}

void FAccelByteLoginPanel::OnUpgradeSuccess(const FAccountUserData& Response)
{
	AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak()]()
	{
		if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
		{
			StrongThis->bRegisterPending = false;
			StrongThis->PendingRegisterUsername.Empty();
			StrongThis->PendingRegisterPassword.Empty();
			StrongThis->bRegisterMode = false;
			StrongThis->SetState(ELoginPanelState::LoggedIn);
			StrongThis->SetError(FString());
			StrongThis->RefreshWidget();
		}
	});
}

void FAccelByteLoginPanel::OnUpgradeError(int32 ErrorCode, const FString& ErrorMessage)
{
	AsyncTask(ENamedThreads::GameThread, [WeakThis = AsWeak(), ErrorCode, ErrorMessage]()
	{
		if (TSharedPtr<FAccelByteLoginPanel> StrongThis = WeakThis.Pin())
		{
			StrongThis->bRegisterPending = false;
			StrongThis->PendingRegisterUsername.Empty();
			StrongThis->PendingRegisterPassword.Empty();
			StrongThis->SetState(ELoginPanelState::LoggedOut);
			StrongThis->SetError(ErrorMessage.IsEmpty() ? FString::Printf(TEXT("Upgrade failed (code %d)"), ErrorCode) : ErrorMessage);
			StrongThis->RefreshWidget();
		}
	});
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (OSS)
	{
		IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
		if (Identity.IsValid())
		{
			Identity->Logout(0);
		}
	}
}

void FAccelByteLoginPanel::OnBackToLoginClicked()
{
	bRegisterMode = false;
	SetError(FString());
	RefreshWidget();
}

void FAccelByteLoginPanel::EnsureWidgetCreated(float Width, float Height)
{
	if (Widget.IsValid())
	{
		return;
	}
	SAssignNew(Widget, SAccelByteLoginWidget)
		.Width(Width)
		.Height(Height)
		.Panel(this);
}

void FAccelByteLoginPanel::RefreshWidget()
{
	if (Widget.IsValid())
	{
		Widget->RequestRefresh();
	}
}

void FAccelByteLoginPanel::SetState(ELoginPanelState NewState)
{
	State = NewState;
	// Broadcast login success when transitioning to LoggedIn state
	if (NewState == ELoginPanelState::LoggedIn)
	{
		// Get the API client to pass to callbacks
		AccelByte::FApiClientPtr ApiClient;
		FOnlineSubsystemAccelByte* ABSubsystem = static_cast<FOnlineSubsystemAccelByte*>(IOnlineSubsystem::Get(ACCELBYTE_SUBSYSTEM));
		if (ABSubsystem)
		{
			ApiClient = ABSubsystem->GetApiClient(0);
		}
		OnLoginSuccessDelegate.Broadcast(ApiClient);
	}
}

void FAccelByteLoginPanel::SetError(const FString& InError)
{
	ErrorText = InError;
}

FDelegateHandle FAccelByteLoginPanel::RegisterOnLoginSuccess(FOnLoginPanelLoginSuccess::FDelegate&& Callback)
{
	FDelegateHandle Handle = OnLoginSuccessDelegate.Add(MoveTemp(Callback));
	
	// If already logged in, fire the callback immediately
	if (IsLoggedIn())
	{
		// Get the API client to pass to the callback
		AccelByte::FApiClientPtr ApiClient;
		FOnlineSubsystemAccelByte* ABSubsystem = static_cast<FOnlineSubsystemAccelByte*>(IOnlineSubsystem::Get(ACCELBYTE_SUBSYSTEM));
		if (ABSubsystem)
		{
			ApiClient = ABSubsystem->GetApiClient(0);
		}
		Callback.Execute(ApiClient);
	}
	return Handle;
}

void FAccelByteLoginPanel::UnregisterOnLoginSuccess(FDelegateHandle Handle)
{
	OnLoginSuccessDelegate.Remove(Handle);
}

void SAccelByteLoginWidget::Construct(const FArguments& InArgs)
{
	Panel = InArgs._Panel;
	Width = InArgs._Width;
	Height = InArgs._Height;

	// Full-screen overlay: centered fixed-size login/register panel + Logout top-right
	ChildSlot
	[
		SNew(SOverlay)
		// Centered fixed-width panel (login form, register form, throbber) — hidden when logged in
		+ SOverlay::Slot()
		.HAlign(HAlign_Center)
		.VAlign(VAlign_Center)
		[
			SNew(SBox)
			.WidthOverride(Width)
			.HeightOverride(Height)
			.Visibility_Lambda([this]() {
				if (Panel && Panel->GetState() == ELoginPanelState::LoggedIn)
				{
					return EVisibility::Collapsed;
				}
				return EVisibility::Visible;
			})
			[
				SNew(SBorder)
				.Padding(12)
				.BorderImage(FCoreStyle::Get().GetBrush("BlackBrush"))
				[
					SAssignNew(ContentContainer, SBox)
				]
			]
		]
		// Logout button in top-right corner
		+ SOverlay::Slot()
		.HAlign(HAlign_Right)
		.VAlign(VAlign_Top)
		.Padding(16.f)
		[
			SNew(SBox)
			.Visibility_Lambda([this]() -> EVisibility {
				if (Panel && Panel->GetState() == ELoginPanelState::LoggedIn)
				{
					return EVisibility::Visible;
				}
				return EVisibility::Collapsed;
			})
			[
				SNew(SButton)
				.Content()
				[
					SNew(STextBlock)
					.Text(NSLOCTEXT("AccelByteLoginPanel", "Logout", "Logout"))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
					.Justification(ETextJustify::Center)
				]
				.OnClicked_Lambda([this]() {
					if (Panel) { Panel->OnLogoutClicked(); }
					return FReply::Handled();
				})
			]
		]
	];
	RequestRefresh();
}

FReply SAccelByteLoginWidget::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
	// Consume so viewport/editor don't see the key (e.g. @ opening console/debug)
	return FReply::Handled();
}

FReply SAccelByteLoginWidget::OnKeyChar(const FGeometry& MyGeometry, const FCharacterEvent& InCharacterEvent)
{
	// Consume so viewport/editor don't see the character (e.g. @)
	return FReply::Handled();
}

void SAccelByteLoginWidget::RequestFocusOnFirstEdit()
{
	if (Panel && Panel->GetState() == ELoginPanelState::LoggedOut && UsernameEdit.IsValid())
	{
		FSlateApplication::Get().SetKeyboardFocus(UsernameEdit.ToSharedRef(), EFocusCause::SetDirectly);
	}
}

void SAccelByteLoginWidget::RequestRefresh()
{
	if (!ContentContainer.IsValid() || !Panel)
	{
		return;
	}
	ContentContainer->SetContent(BuildContent());
	// Keep keyboard focus on the first text box when showing login/register form so input isn't stolen by the editor
	if (Panel->GetState() == ELoginPanelState::LoggedOut && UsernameEdit.IsValid())
	{
		FSlateApplication::Get().SetKeyboardFocus(UsernameEdit.ToSharedRef(), EFocusCause::SetDirectly);
	}
}

TSharedRef<SWidget> SAccelByteLoginWidget::BuildContent()
{
	if (!Panel)
	{
		return SNew(STextBlock).Text(NSLOCTEXT("AccelByteLoginPanel", "NoPanel", "No panel"));
	}
	const ELoginPanelState State = Panel->GetState();
	if (State == ELoginPanelState::LoggingIn || State == ELoginPanelState::LoggingOut)
	{
		return BuildThrobberOverlay();
	}
	if (State == ELoginPanelState::LoggedIn)
	{
		return BuildLoggedInContent();
	}
	if (Panel->IsRegisterMode())
	{
		return BuildRegisterForm();
	}
	return BuildLoginForm();
}

TSharedRef<SWidget> SAccelByteLoginWidget::BuildLoginForm()
{
	UsernameEdit.Reset();
	PasswordEdit.Reset();
	DisplayNameEdit.Reset();
	return SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 0, 0, 12)
		[
			SNew(STextBlock)
			.Text(NSLOCTEXT("AccelByteLoginPanel", "LoginTitle", "Login"))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelTitleFontSize))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 6)
		[
			SNew(SBox)
			.HeightOverride(LoginPanelEditBoxHeight)
			[
				SAssignNew(UsernameEdit, SEditableTextBox)
				.HintText(NSLOCTEXT("AccelByteLoginPanel", "UsernameHint", "Username"))
				.Text(Panel ? FText::FromString(Panel->GetStoredUsername()) : FText::GetEmpty())
				.MinDesiredWidth(200.f)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
				.OnTextChanged_Lambda([this](const FText& NewText) {
					if (Panel) { Panel->SetStoredUsername(NewText.ToString()); }
				})
			]
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 6)
		[
			SNew(SBox)
			.HeightOverride(LoginPanelEditBoxHeight)
			[
				SAssignNew(PasswordEdit, SEditableTextBox)
				.HintText(NSLOCTEXT("AccelByteLoginPanel", "PasswordHint", "Password"))
				.Text(Panel ? FText::FromString(Panel->GetStoredPassword()) : FText::GetEmpty())
				.IsPassword(true)
				.MinDesiredWidth(200.f)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
				.OnTextChanged_Lambda([this](const FText& NewText) {
					if (Panel) { Panel->SetStoredPassword(NewText.ToString()); }
				})
			]
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 8, 0, 0)
		[
			SNew(STextBlock)
			.Text_Lambda([this]() { return Panel ? FText::FromString(Panel->GetErrorText()) : FText::GetEmpty(); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
			.ColorAndOpacity(FSlateColor(FLinearColor(1.f, 0.3f, 0.3f)))
			.AutoWrapText(true)
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 12, 0, 6)
		[
			SNew(SButton)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteLoginPanel", "LoginButton", "Login"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel && UsernameEdit.IsValid() && PasswordEdit.IsValid())
				{
					FString U = UsernameEdit->GetText().ToString();
					FString P = PasswordEdit->GetText().ToString();
					Panel->SetStoredUsername(U);
					Panel->SetStoredPassword(P);
					Panel->OnLoginClicked(U, P);
				}
				return FReply::Handled();
			})
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 0)
		[
			SNew(SButton)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteLoginPanel", "RegisterButton", "Register"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel) { Panel->SetRegisterMode(true); }
				return FReply::Handled();
			})
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 0)
		[
			SNew(SButton)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteLoginPanel", "GuestLoginButton", "Login as Guest"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel) { Panel->OnDeviceIdLoginClicked(); }
				return FReply::Handled();
			})
		];
}

TSharedRef<SWidget> SAccelByteLoginWidget::BuildRegisterForm()
{
	UsernameEdit.Reset();
	PasswordEdit.Reset();
	DisplayNameEdit.Reset();
	return SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 0, 0, 12)
		[
			SNew(STextBlock)
			.Text(NSLOCTEXT("AccelByteLoginPanel", "RegisterTitle", "Register"))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelTitleFontSize))
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 6)
		[
			SNew(SBox)
			.HeightOverride(LoginPanelEditBoxHeight)
			[
				SAssignNew(UsernameEdit, SEditableTextBox)
				.HintText(NSLOCTEXT("AccelByteLoginPanel", "RegisterUsernameHint", "Username"))
				.Text(Panel ? FText::FromString(Panel->GetStoredUsername()) : FText::GetEmpty())
				.MinDesiredWidth(200.f)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
				.OnTextChanged_Lambda([this](const FText& NewText) {
					if (Panel) { Panel->SetStoredUsername(NewText.ToString()); }
				})
			]
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 6)
		[
			SNew(SBox)
			.HeightOverride(LoginPanelEditBoxHeight)
			[
				SAssignNew(PasswordEdit, SEditableTextBox)
				.HintText(NSLOCTEXT("AccelByteLoginPanel", "RegisterPasswordHint", "Password"))
				.Text(Panel ? FText::FromString(Panel->GetStoredPassword()) : FText::GetEmpty())
				.IsPassword(true)
				.MinDesiredWidth(200.f)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
				.OnTextChanged_Lambda([this](const FText& NewText) {
					if (Panel) { Panel->SetStoredPassword(NewText.ToString()); }
				})
			]
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 6)
		[
			SNew(SBox)
			.HeightOverride(LoginPanelEditBoxHeight)
			[
				SAssignNew(DisplayNameEdit, SEditableTextBox)
				.HintText(NSLOCTEXT("AccelByteLoginPanel", "DisplayNameHint", "Display Name (optional)"))
				.Text(Panel ? FText::FromString(Panel->GetStoredDisplayName()) : FText::GetEmpty())
				.MinDesiredWidth(200.f)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
				.OnTextChanged_Lambda([this](const FText& NewText) {
					if (Panel) { Panel->SetStoredDisplayName(NewText.ToString()); }
				})
			]
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 8, 0, 0)
		[
			SNew(STextBlock)
			.Text_Lambda([this]() { return Panel ? FText::FromString(Panel->GetErrorText()) : FText::GetEmpty(); })
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
			.ColorAndOpacity(FSlateColor(FLinearColor(1.f, 0.3f, 0.3f)))
			.AutoWrapText(true)
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 12, 0, 6)
		[
			SNew(SButton)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteLoginPanel", "RegisterSubmitButton", "Register"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel && UsernameEdit.IsValid() && PasswordEdit.IsValid())
				{
					FString U = UsernameEdit->GetText().ToString();
					FString P = PasswordEdit->GetText().ToString();
					FString D = DisplayNameEdit.IsValid() ? DisplayNameEdit->GetText().ToString() : FString();
					Panel->SetStoredUsername(U);
					Panel->SetStoredPassword(P);
					Panel->SetStoredDisplayName(D);
					Panel->OnRegisterClicked(U, P, D);
				}
				return FReply::Handled();
			})
		]
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 6, 0, 0)
		[
			SNew(SButton)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteLoginPanel", "BackToLogin", "Back to Login"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", LoginPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel) { Panel->OnBackToLoginClicked(); }
				return FReply::Handled();
			})
		];
}

TSharedRef<SWidget> SAccelByteLoginWidget::BuildThrobberOverlay()
{
	return SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.FillHeight(1.f)
		.VAlign(VAlign_Center)
		.HAlign(HAlign_Center)
		[
			SNew(SBox)
			.WidthOverride(48.f)
			.HeightOverride(48.f)
			[
				SNew(SThrobber)
			]
		];
}

TSharedRef<SWidget> SAccelByteLoginWidget::BuildLoggedInContent()
{
	return SNew(SVerticalBox)
		+ SVerticalBox::Slot()
		.FillHeight(1.f)
		.VAlign(VAlign_Center)
		.HAlign(HAlign_Center)
		[
			SNew(STextBlock)
			.Text(NSLOCTEXT("AccelByteLoginPanel", "LoggedIn", "You are logged in."))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", LoginPanelBodyFontSize))
		];
}
