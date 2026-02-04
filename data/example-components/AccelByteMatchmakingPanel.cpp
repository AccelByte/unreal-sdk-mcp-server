// AccelByte matchmaking panel - implementation

// AB_MCP_BEGIN:AccelByte.Matchmaking.Panel
// {
//   "service": "matchmaking",
//   "provider": "accelbyte",
//   "language": "unreal-cpp",
//   "description": "Self-contained Unreal Slate UI panel for AccelByte P2P matchmaking: Quick Play with automatic party session creation, session restoration, match finding, and session joining. Covers matchmaking, sessions, multiplayer, online play, party system, lobby management.",
//   "keywords": ["matchmaking", "sessions", "multiplayer", "P2P", "peer-to-peer", "quick play", "party", "lobby", "join", "search", "find match", "online play", "game session", "party session", "cancel matchmaking"],
//   "controllerClass": "FAccelByteMatchmakingPanel",
//   "uiWidgetClass": "SAccelByteMatchmakingWidget",
//   "stateEnum": "EMatchmakingPanelState",
//   "publicInterface": {
//     "initialise": "void Initialise()",
//     "show": "void Show(float Width = 400.f, float Height = 300.f)",
//     "hide": "void Hide()",
//     "buildWidget": "TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 300.f)",
//     "onQuickPlayClicked": "void OnQuickPlayClicked()",
//     "onCancelClicked": "void OnCancelClicked()"
//   },
//   "asyncState": {
//     "stateField": "State",
//     "matchmakingSessionNameField": "MatchmakingSessionName",
//     "partySessionNameField": "PartySessionName",
//     "searchHandleField": "SearchHandle"
//   },
//   "moduleDependencies": ["Slate", "SlateCore", "OnlineSubsystem"],
//   "engineConfiguration": {
//     "DefaultEngine.ini": {
//       "OnlineSubsystemAccelByte": {
//         "bAutoLobbyConnectAfterLoginSuccess": "true",
//         "bEnableV2Sessions": "true"
//       },
//       "AccelByteNetworkUtilities": {
//         "bNonSeamlessTravelUseNewConnection": "true",
//         "HostCheckTimeout": "5",
//         "UseTurnManager": "true"
//       }
//     }
//   },
//   "integrationHints": ["Install the AccelByte Unreal SDK first (use the install_unreal_sdk tool) if not already installed. Then add these to PublicDependencyModuleNames in your module's .Build.cs: Slate, SlateCore, OnlineSubsystem (for session/matchmaking), and your AccelByte SDK module. Required DefaultEngine.ini settings: [OnlineSubsystemAccelByte] bAutoLobbyConnectAfterLoginSuccess=true, bEnableV2Sessions=true; [AccelByteNetworkUtilities] bNonSeamlessTravelUseNewConnection=true, HostCheckTimeout=5, UseTurnManager=true."]
// }
// AB_MCP_END:AccelByte.Matchmaking.Panel

#include "AccelByteMatchmakingPanel.h"
#include "Async/Async.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/OnlineIdentityInterface.h"
#include "OnlineSubsystemAccelByte.h"
#include "OnlineSessionInterfaceV2AccelByte.h"
#include "OnlineSubsystemAccelByteSessionSettings.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Images/SThrobber.h"

namespace
{
	const int32 MatchmakingPanelTitleFontSize = 44;
	const int32 MatchmakingPanelBodyFontSize = 22;
	const int32 MatchmakingPanelButtonFontSize = 22;
	const FName DefaultMatchmakingSessionName = FName(TEXT("GameSession"));
	const FName DefaultPartySessionName = FName(TEXT("PartySession"));
	const FString DefaultMatchPool = TEXT("default");
}

void FAccelByteMatchmakingPanel::Initialise()
{
	State = EMatchmakingPanelState::Idle;
	StatusText = TEXT("Ready to play");
	ErrorText.Empty();
	MatchmakingSessionName = DefaultMatchmakingSessionName;
}

FAccelByteMatchmakingPanel::~FAccelByteMatchmakingPanel()
{
	// Critical: Unbind all delegates before destruction to prevent dangling pointer callbacks
	UnbindDelegates();
	
	// Hide and clear widget to ensure proper cleanup
	if (bVisible)
	{
		Hide();
	}
	Widget.Reset();
	RootWidget.Reset();
	SearchHandle.Reset();
}

void FAccelByteMatchmakingPanel::Show(float Width, float Height)
{
	if (bVisible)
	{
		return;
	}
	if (!GEngine || !GEngine->GameViewport)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::Show - No GameViewport available"));
		return;
	}
	EnsureWidgetCreated(Width, Height);
	if (!Widget.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::Show - Widget creation failed"));
		return;
	}
	RootWidget = Widget;
	GEngine->GameViewport->AddViewportWidgetContent(Widget.ToSharedRef());
	bVisible = true;
	RefreshWidget();
}

void FAccelByteMatchmakingPanel::Hide()
{
	if (!bVisible)
	{
		return;
	}
	if (GEngine && GEngine->GameViewport && Widget.IsValid())
	{
		GEngine->GameViewport->RemoveViewportWidgetContent(Widget.ToSharedRef());
	}
	bVisible = false;
}

TSharedPtr<SWidget> FAccelByteMatchmakingPanel::GetWidget() const
{
	return Widget;
}

TSharedRef<SWidget> FAccelByteMatchmakingPanel::BuildWidget(float Width, float Height)
{
	EnsureWidgetCreated(Width, Height);
	check(Widget.IsValid());
	return Widget.ToSharedRef();
}

void FAccelByteMatchmakingPanel::OnQuickPlayClicked()
{
	if (!CanStartMatchmaking())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::OnQuickPlayClicked - Cannot start matchmaking in current state"));
		return;
	}

	// Unbind any existing delegates
	UnbindDelegates();
	SetError(FString());

	// First restore any existing sessions from the backend
	UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnQuickPlayClicked - Restoring active sessions first"));
	RestorePartySessions();
}

bool FAccelByteMatchmakingPanel::IsInPartySession() const
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		return false;
	}

	IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
	if (!SessionInterface.IsValid())
	{
		return false;
	}

	// Check if we already have a party session
	FNamedOnlineSession* ExistingParty = SessionInterface->GetNamedSession(DefaultPartySessionName);
	return (ExistingParty != nullptr);
}

void FAccelByteMatchmakingPanel::RestorePartySessions()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}

	FOnlineSessionV2AccelBytePtr ABSessionInterface = StaticCastSharedPtr<FOnlineSessionV2AccelByte>(OSS->GetSessionInterface());
	if (!ABSessionInterface.IsValid())
	{
		SetError(TEXT("Session interface not available"));
		return;
	}

	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity interface not available"));
		return;
	}

	FUniqueNetIdPtr LocalUserId = Identity->GetUniquePlayerId(0);
	if (!LocalUserId.IsValid())
	{
		SetError(TEXT("Not logged in"));
		return;
	}

	SetState(EMatchmakingPanelState::RestoringParties);
	SetStatus(TEXT("Restoring sessions..."));
	RefreshWidget();

	UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::RestorePartySessions - Calling RestoreActiveSessions"));

	// Restore all active sessions from the backend
	TWeakPtr<FAccelByteMatchmakingPanel> WeakSelf = AsShared();
	ABSessionInterface->RestoreActiveSessions(*LocalUserId,
		FOnRestoreActiveSessionsComplete::CreateLambda([WeakSelf](const FUniqueNetId& UserId, const FOnlineError& Result)
		{
			if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakSelf.Pin())
			{
				StrongThis->OnRestoreActiveSessionsComplete(UserId, Result);
			}
		}));
}

void FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete(const FUniqueNetId& LocalUserId, const FOnlineError& Result)
{
	UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - Success: %s, Error: %s"),
		Result.bSucceeded ? TEXT("true") : TEXT("false"),
		*Result.ErrorMessage.ToString());

	if (!Result.bSucceeded)
	{
		// Even if restore fails, we can still try to proceed - the backend might just not have any sessions
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - Restore failed but continuing: %s"), *Result.ErrorMessage.ToString());
	}

	// Check if we now have a party session (either existing local or restored)
	if (IsInPartySession())
	{
		UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - Found existing party session, starting matchmaking"));
		StartMatchmakingInternal();
	}
	else
	{
		// Check if the session interface recognizes us as being in a party (includes restored sessions)
		IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
		if (OSS)
		{
			FOnlineSessionV2AccelBytePtr ABSessionInterface = StaticCastSharedPtr<FOnlineSessionV2AccelByte>(OSS->GetSessionInterface());
			if (ABSessionInterface.IsValid())
			{
				// Check if AccelByte session interface thinks we're in a party
				if (ABSessionInterface->IsInPartySession())
				{
					UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - ABSessionInterface reports we are in a party session"));
					StartMatchmakingInternal();
					return;
				}

				// Check for restored party sessions that need to be joined
				TArray<FOnlineRestoredSessionAccelByte> RestoredParties = ABSessionInterface->GetAllRestoredPartySessions();
				if (RestoredParties.Num() > 0)
				{
					UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - Found %d restored party sessions, leaving them to create fresh party"), RestoredParties.Num());
					
					// Leave the restored party session so we can create a new one
					// For simplicity, we'll just create a new party - in production you might want to rejoin
					const FOnlineRestoredSessionAccelByte& RestoredParty = RestoredParties[0];
					TWeakPtr<FAccelByteMatchmakingPanel> WeakThisLeave = AsShared();
					ABSessionInterface->LeaveRestoredSession(LocalUserId, RestoredParty, 
						FOnLeaveSessionComplete::CreateLambda([WeakThisLeave](bool bSuccess, FString SessionId)
						{
							UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel - Left restored party session %s, success: %s"), *SessionId, bSuccess ? TEXT("true") : TEXT("false"));
							if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakThisLeave.Pin())
							{
								StrongThis->CreatePartySession();
							}
						}));
					return;
				}
			}
		}

		// No existing party, create a new one
		UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnRestoreActiveSessionsComplete - No existing party found, creating new one"));
		CreatePartySession();
	}
}

void FAccelByteMatchmakingPanel::CreatePartySession()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}

	IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
	if (!SessionInterface.IsValid())
	{
		SetError(TEXT("Session interface not available"));
		return;
	}

	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity interface not available"));
		return;
	}

	FUniqueNetIdPtr LocalUserId = Identity->GetUniquePlayerId(0);
	if (!LocalUserId.IsValid())
	{
		SetError(TEXT("Not logged in"));
		return;
	}

	// Bind create session delegate
	TWeakPtr<FAccelByteMatchmakingPanel> WeakThisCreate = AsShared();
	CreateSessionCompleteHandle = SessionInterface->AddOnCreateSessionCompleteDelegate_Handle(
		FOnCreateSessionCompleteDelegate::CreateLambda([WeakThisCreate](FName SessionName, bool bWasSuccessful)
		{
			if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakThisCreate.Pin())
			{
				StrongThis->OnCreateSessionComplete(SessionName, bWasSuccessful);
			}
		}));

	// Setup party session settings
	FOnlineSessionSettings PartySettings;
	PartySettings.bIsLANMatch = false;
	PartySettings.bShouldAdvertise = false;
	PartySettings.bUsesPresence = true;
	PartySettings.NumPublicConnections = 4;
	PartySettings.Set(SETTING_SESSION_TYPE, FString(SETTING_SESSION_TYPE_PARTY_SESSION), EOnlineDataAdvertisementType::ViaOnlineService);
	// SETTING_SESSION_TEMPLATE_NAME - must match a party session template configured in AccelByte Admin Portal
	PartySettings.Set(FName(TEXT("SESSIONTEMPLATENAME")), FString(TEXT("lobby")), EOnlineDataAdvertisementType::ViaOnlineService);

	PartySessionName = DefaultPartySessionName;

	SetState(EMatchmakingPanelState::CreatingParty);
	SetStatus(TEXT("Creating party..."));
	RefreshWidget();

	UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::CreatePartySession - Creating party session"));

	bool bCreated = SessionInterface->CreateSession(*LocalUserId, PartySessionName, PartySettings);
	if (!bCreated)
	{
		SessionInterface->ClearOnCreateSessionCompleteDelegate_Handle(CreateSessionCompleteHandle);
		CreateSessionCompleteHandle.Reset();
		SetState(EMatchmakingPanelState::Error);
		SetError(TEXT("Failed to create party session"));
		RefreshWidget();
		UE_LOG(LogTemp, Error, TEXT("FAccelByteMatchmakingPanel::CreatePartySession - CreateSession returned false"));
	}
}

void FAccelByteMatchmakingPanel::OnCreateSessionComplete(FName SessionName, bool bWasSuccessful)
{
	// Clear the delegate
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (OSS)
	{
		IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
		if (SessionInterface.IsValid() && CreateSessionCompleteHandle.IsValid())
		{
			SessionInterface->ClearOnCreateSessionCompleteDelegate_Handle(CreateSessionCompleteHandle);
			CreateSessionCompleteHandle.Reset();
		}
	}

	if (!bWasSuccessful)
	{
		SetState(EMatchmakingPanelState::Error);
		SetError(TEXT("Failed to create party session"));
		RefreshWidget();
		UE_LOG(LogTemp, Error, TEXT("FAccelByteMatchmakingPanel::OnCreateSessionComplete - Party creation failed"));
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnCreateSessionComplete - Party session created, starting matchmaking"));

	// Now start matchmaking
	StartMatchmakingInternal();
}

void FAccelByteMatchmakingPanel::StartMatchmakingInternal()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}

	IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
	if (!SessionInterface.IsValid())
	{
		SetError(TEXT("Session interface not available"));
		return;
	}

	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity interface not available"));
		return;
	}

	FUniqueNetIdPtr LocalUserId = Identity->GetUniquePlayerId(0);
	if (!LocalUserId.IsValid())
	{
		SetError(TEXT("Not logged in"));
		return;
	}

	// Create AccelByte-specific search handle
	SearchHandle = MakeShared<FOnlineSessionSearchAccelByte>();
	SearchHandle->bIsLanQuery = false;
	SearchHandle->MaxSearchResults = 1;
	SearchHandle->SetIsP2PMatchmaking(true);
	// Set the match pool via QuerySettings
	SearchHandle->QuerySettings.Set(SETTING_SESSION_MATCHPOOL, DefaultMatchPool, EOnlineComparisonOp::Equals);

	// Setup session settings
	FOnlineSessionSettings SessionSettings;
	SessionSettings.bIsLANMatch = false;
	SessionSettings.bShouldAdvertise = true;
	SessionSettings.bUsesPresence = true;
	SessionSettings.NumPublicConnections = 2;

	// Create matchmaking user
	TArray<FSessionMatchmakingUser> LocalPlayers;
	FSessionMatchmakingUser LocalPlayer{LocalUserId.ToSharedRef(), FOnlineKeyValuePairs<FString, FVariantData>()};
	LocalPlayers.Add(LocalPlayer);

	// Bind join session delegate
	TWeakPtr<FAccelByteMatchmakingPanel> WeakThisMatchmaking = AsShared();
	JoinSessionCompleteHandle = SessionInterface->AddOnJoinSessionCompleteDelegate_Handle(
		FOnJoinSessionCompleteDelegate::CreateLambda([WeakThisMatchmaking](FName SessionName, EOnJoinSessionCompleteResult::Type Result)
		{
			if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakThisMatchmaking.Pin())
			{
				StrongThis->OnJoinSessionComplete(SessionName, Result);
			}
		}));

	// Bind cancel matchmaking delegate
	CancelMatchmakingCompleteHandle = SessionInterface->AddOnCancelMatchmakingCompleteDelegate_Handle(
		FOnCancelMatchmakingCompleteDelegate::CreateLambda([WeakThisMatchmaking](FName SessionName, bool bWasSuccessful)
		{
			if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakThisMatchmaking.Pin())
			{
				StrongThis->OnCancelMatchmakingComplete(SessionName, bWasSuccessful);
			}
		}));

	// Create completion delegate
	FOnStartMatchmakingComplete CompletionDelegate = FOnStartMatchmakingComplete::CreateLambda(
		[WeakThisMatchmaking](FName SessionName, const FOnlineError& ErrorDetails, const FSessionMatchmakingResults& Results)
		{
			if (TSharedPtr<FAccelByteMatchmakingPanel> StrongThis = WeakThisMatchmaking.Pin())
			{
				StrongThis->OnStartMatchmakingComplete(SessionName, ErrorDetails, Results);
			}
		});

	// Cast to AccelByte session interface to use the AccelByte-specific StartMatchmaking
	TSharedRef<FOnlineSessionSearch> BaseSearchHandle = SearchHandle.ToSharedRef();

	bool bStarted = SessionInterface->StartMatchmaking(LocalPlayers, MatchmakingSessionName, SessionSettings, BaseSearchHandle, CompletionDelegate);

	if (bStarted)
	{
		SetState(EMatchmakingPanelState::Searching);
		SetStatus(TEXT("Searching for match..."));
		SetError(FString());
		UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::StartMatchmakingInternal - Matchmaking started"));
	}
	else
	{
		SetState(EMatchmakingPanelState::Error);
		SetError(TEXT("Failed to start matchmaking"));
		UE_LOG(LogTemp, Error, TEXT("FAccelByteMatchmakingPanel::StartMatchmakingInternal - Failed to start matchmaking"));
	}

	RefreshWidget();
}

void FAccelByteMatchmakingPanel::OnCancelClicked()
{
	if (!CanCancel())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::OnCancelClicked - Cannot cancel in current state"));
		return;
	}

	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (!OSS)
	{
		SetError(TEXT("Online subsystem not available"));
		return;
	}

	IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
	if (!SessionInterface.IsValid())
	{
		SetError(TEXT("Session interface not available"));
		return;
	}

	IOnlineIdentityPtr Identity = OSS->GetIdentityInterface();
	if (!Identity.IsValid())
	{
		SetError(TEXT("Identity interface not available"));
		return;
	}

	FUniqueNetIdPtr LocalUserId = Identity->GetUniquePlayerId(0);
	if (!LocalUserId.IsValid())
	{
		SetError(TEXT("Not logged in"));
		return;
	}

	SetState(EMatchmakingPanelState::Cancelling);
	SetStatus(TEXT("Cancelling..."));
	RefreshWidget();

	bool bCancelled = SessionInterface->CancelMatchmaking(*LocalUserId, MatchmakingSessionName);
	if (!bCancelled)
	{
		// If cancel call fails immediately, reset to idle
		SetState(EMatchmakingPanelState::Idle);
		SetStatus(TEXT("Ready to play"));
		RefreshWidget();
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteMatchmakingPanel::OnCancelClicked - CancelMatchmaking returned false"));
	}
}

void FAccelByteMatchmakingPanel::OnStartMatchmakingComplete(FName SessionName, const FOnlineError& ErrorDetails, const FSessionMatchmakingResults& Results)
{
	AsyncTask(ENamedThreads::GameThread, [this, SessionName, ErrorDetails, Results]()
	{
		if (!ErrorDetails.bSucceeded)
		{
			SetState(EMatchmakingPanelState::Error);
			SetStatus(TEXT("Matchmaking failed"));
			SetError(ErrorDetails.ErrorMessage.ToString());
			UE_LOG(LogTemp, Error, TEXT("FAccelByteMatchmakingPanel::OnStartMatchmakingComplete - Failed: %s"), *ErrorDetails.ErrorMessage.ToString());
			RefreshWidget();
			return;
		}

		// Match found!
		SetState(EMatchmakingPanelState::MatchFound);
		SetStatus(TEXT("Match found!"));
		SetError(FString());
		UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnStartMatchmakingComplete - Match found for session %s"), *SessionName.ToString());
		RefreshWidget();

		// Auto-join the session
		if (SearchHandle.IsValid() && SearchHandle->SearchResults.Num() > 0)
		{
			SetState(EMatchmakingPanelState::Joining);
			SetStatus(TEXT("Joining match..."));
			RefreshWidget();

			IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
			if (OSS)
			{
				IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
				if (SessionInterface.IsValid())
				{
					bool bJoining = SessionInterface->JoinSession(0, SessionName, SearchHandle->SearchResults[0]);
					if (!bJoining)
					{
						SetState(EMatchmakingPanelState::Error);
						SetStatus(TEXT("Failed to join"));
						SetError(TEXT("JoinSession call failed"));
						RefreshWidget();
					}
				}
			}
		}
		else
		{
			// No search results but matchmaking succeeded - session may have been auto-joined
			SetState(EMatchmakingPanelState::InSession);
			SetStatus(TEXT("In session"));
			RefreshWidget();
		}
	});
}

void FAccelByteMatchmakingPanel::OnJoinSessionComplete(FName SessionName, EOnJoinSessionCompleteResult::Type Result)
{
	AsyncTask(ENamedThreads::GameThread, [this, SessionName, Result]()
	{
		if (Result == EOnJoinSessionCompleteResult::Success)
		{
			SetState(EMatchmakingPanelState::InSession);
			SetStatus(TEXT("In session - Ready to play!"));
			SetError(FString());
			UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnJoinSessionComplete - Successfully joined session %s"), *SessionName.ToString());
		}
		else
		{
			SetState(EMatchmakingPanelState::Error);
			SetStatus(TEXT("Failed to join session"));
			
			FString ErrorMsg;
			switch (Result)
			{
			case EOnJoinSessionCompleteResult::SessionIsFull:
				ErrorMsg = TEXT("Session is full");
				break;
			case EOnJoinSessionCompleteResult::SessionDoesNotExist:
				ErrorMsg = TEXT("Session does not exist");
				break;
			case EOnJoinSessionCompleteResult::CouldNotRetrieveAddress:
				ErrorMsg = TEXT("Could not retrieve address");
				break;
			case EOnJoinSessionCompleteResult::AlreadyInSession:
				ErrorMsg = TEXT("Already in session");
				break;
			default:
				ErrorMsg = TEXT("Unknown error");
				break;
			}
			SetError(ErrorMsg);
			UE_LOG(LogTemp, Error, TEXT("FAccelByteMatchmakingPanel::OnJoinSessionComplete - Failed to join session: %s"), *ErrorMsg);
		}
		RefreshWidget();
	});
}

void FAccelByteMatchmakingPanel::OnCancelMatchmakingComplete(FName SessionName, bool bWasSuccessful)
{
	AsyncTask(ENamedThreads::GameThread, [this, SessionName, bWasSuccessful]()
	{
		SetState(EMatchmakingPanelState::Idle);
		SetStatus(TEXT("Ready to play"));
		SetError(FString());
		SearchHandle.Reset();
		UE_LOG(LogTemp, Log, TEXT("FAccelByteMatchmakingPanel::OnCancelMatchmakingComplete - Cancelled: %s"), bWasSuccessful ? TEXT("Success") : TEXT("Failed"));
		RefreshWidget();
	});
}

void FAccelByteMatchmakingPanel::SetState(EMatchmakingPanelState NewState)
{
	State = NewState;
}

void FAccelByteMatchmakingPanel::SetStatus(const FString& InStatus)
{
	StatusText = InStatus;
}

void FAccelByteMatchmakingPanel::SetError(const FString& InError)
{
	ErrorText = InError;
}

void FAccelByteMatchmakingPanel::EnsureWidgetCreated(float Width, float Height)
{
	if (!Widget.IsValid())
	{
		Widget = SNew(SAccelByteMatchmakingWidget)
			.Width(Width)
			.Height(Height)
			.Panel(this);
	}
}

void FAccelByteMatchmakingPanel::RefreshWidget()
{
	if (Widget.IsValid())
	{
		Widget->RequestRefresh();
	}
}

void FAccelByteMatchmakingPanel::UnbindDelegates()
{
	IOnlineSubsystem* OSS = IOnlineSubsystem::Get();
	if (OSS)
	{
		IOnlineSessionPtr SessionInterface = OSS->GetSessionInterface();
		if (SessionInterface.IsValid())
		{
			if (CreateSessionCompleteHandle.IsValid())
			{
				SessionInterface->ClearOnCreateSessionCompleteDelegate_Handle(CreateSessionCompleteHandle);
				CreateSessionCompleteHandle.Reset();
			}
			if (JoinSessionCompleteHandle.IsValid())
			{
				SessionInterface->ClearOnJoinSessionCompleteDelegate_Handle(JoinSessionCompleteHandle);
				JoinSessionCompleteHandle.Reset();
			}
			if (CancelMatchmakingCompleteHandle.IsValid())
			{
				SessionInterface->ClearOnCancelMatchmakingCompleteDelegate_Handle(CancelMatchmakingCompleteHandle);
				CancelMatchmakingCompleteHandle.Reset();
			}
		}
	}
}

// ============================================================================
// SAccelByteMatchmakingWidget
// ============================================================================

void SAccelByteMatchmakingWidget::Construct(const FArguments& InArgs)
{
	Panel = InArgs._Panel;
	Width = InArgs._Width;
	Height = InArgs._Height;

	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()
		.HAlign(HAlign_Center)
		.VAlign(VAlign_Center)
		[
			SNew(SBox)
			.WidthOverride(Width)
			.HeightOverride(Height)
			[
				SNew(SBorder)
				.BorderImage(FCoreStyle::Get().GetBrush("ToolPanel.GroupBorder"))
				.Padding(16.f)
				[
					SAssignNew(ContentContainer, SBox)
					[
						BuildContent()
					]
				]
			]
		]
	];
}

void SAccelByteMatchmakingWidget::RequestRefresh()
{
	if (ContentContainer.IsValid())
	{
		ContentContainer->SetContent(BuildContent());
	}
}

TSharedRef<SWidget> SAccelByteMatchmakingWidget::BuildContent()
{
	if (!Panel)
	{
		return SNullWidget::NullWidget;
	}

	const bool bIsSearching = Panel->IsSearching() || Panel->GetState() == EMatchmakingPanelState::MatchFound || Panel->GetState() == EMatchmakingPanelState::Joining;
	const bool bCanStart = Panel->CanStartMatchmaking();
	const bool bCanCancel = Panel->CanCancel();

	return SNew(SVerticalBox)
		// Title
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 0, 0, 12)
		[
			SNew(STextBlock)
			.Text(NSLOCTEXT("AccelByteMatchmakingPanel", "Title", "Play Online"))
			.Font(FCoreStyle::GetDefaultFontStyle("Bold", MatchmakingPanelTitleFontSize))
		]
		// Status text
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 8, 0, 8)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.VAlign(VAlign_Center)
			[
				SNew(STextBlock)
				.Text(FText::FromString(Panel->GetStatusText()))
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", MatchmakingPanelBodyFontSize))
			]
			+ SHorizontalBox::Slot()
			.AutoWidth()
			.Padding(8, 0, 0, 0)
			.VAlign(VAlign_Center)
			[
				SNew(SBox)
				.Visibility(bIsSearching ? EVisibility::Visible : EVisibility::Collapsed)
				[
					SNew(SCircularThrobber)
					.Radius(12.f)
				]
			]
		]
		// Error text
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 4, 0, 8)
		[
			SNew(STextBlock)
			.Text(FText::FromString(Panel->GetErrorText()))
			.Font(FCoreStyle::GetDefaultFontStyle("Regular", MatchmakingPanelBodyFontSize))
			.ColorAndOpacity(FSlateColor(FLinearColor(1.f, 0.3f, 0.3f)))
			.AutoWrapText(true)
			.Visibility(Panel->GetErrorText().IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible)
		]
		// Spacer
		+ SVerticalBox::Slot()
		.FillHeight(1.0f)
		[
			SNew(SSpacer)
		]
		// Quick Play button
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 4, 0, 4)
		[
			SNew(SButton)
			.IsEnabled(bCanStart)
			.Visibility(bCanCancel ? EVisibility::Collapsed : EVisibility::Visible)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteMatchmakingPanel", "QuickPlayButton", "Quick Play"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", MatchmakingPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel) { Panel->OnQuickPlayClicked(); }
				return FReply::Handled();
			})
		]
		// Cancel button
		+ SVerticalBox::Slot()
		.AutoHeight()
		.Padding(0, 4, 0, 4)
		[
			SNew(SButton)
			.IsEnabled(bCanCancel)
			.Visibility(bCanCancel ? EVisibility::Visible : EVisibility::Collapsed)
			.Content()
			[
				SNew(STextBlock)
				.Text(NSLOCTEXT("AccelByteMatchmakingPanel", "CancelButton", "Cancel"))
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", MatchmakingPanelButtonFontSize))
				.Justification(ETextJustify::Center)
			]
			.OnClicked_Lambda([this]() {
				if (Panel) { Panel->OnCancelClicked(); }
				return FReply::Handled();
			})
		];
}
