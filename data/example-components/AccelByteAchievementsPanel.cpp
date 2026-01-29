// AccelByte achievements debug panel - implementation

#include "AccelByteAchievementsPanel.h"

#include "Async/Async.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "TextureResource.h"
#include "Engine/Texture2D.h"

using namespace AccelByte;
using namespace AccelByte::Api;

// AB_MCP_BEGIN:AccelByte.Achievements.SDK
// {
//   "controllerClass": "FAccelByteAchievementsPanel",
//   "apiNamespace": "AccelByte::Api",
//   "apiClass": "Achievement",
//   "apiClientGetter": "ApiClient->GetApiPtr<Achievement>()",
//   "definitionQuery": {
//     "method": "QueryAchievements",
//     "params": [
//       "Language",
//       "EAccelByteAchievementListSortBy::NONE",
//       "OnSuccess",
//       "OnError",
//       "0",
//       "100"
//     ],
//     "successCallback": "OnQueryDefinitionsSuccess",
//     "errorCallback": "OnAccelByteError"
//   },
//   "userQuery": {
//     "method": "QueryUserAchievements",
//     "params": [
//       "EAccelByteAchievementListSortBy::NONE",
//       "OnSuccess",
//       "OnError",
//       "0",
//       "100",
//       "true",
//       "\"\""
//     ],
//     "successCallback": "OnQueryUserAchievementsSuccess",
//     "errorCallback": "OnAccelByteError"
//   },
//   "iconDownload": {
//     "httpModule": "FHttpModule::Get()",
//     "requestSetup": "SetURL(IconUrl); SetVerb(\"GET\")",
//     "completionCallback": "OnIconDownloadComplete",
//     "textureType": "UTexture2D*",
//     "brushField": "FAccelByteAchievementEntry::IconBrush"
//   }
// }
// AB_MCP_END:AccelByte.Achievements.SDK

void FAccelByteAchievementsPanel::Initialise(FApiClientPtr InApiClient, const FString& InLanguage)
{
	ApiClient = InApiClient;
	Language = InLanguage;

	if (!ApiClient.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Initialise - ApiClient is invalid"));
		return;
	}

	Entries.Empty();
	CodeToIndex.Empty();
	bDefinitionsLoaded = false;
	bPendingUserUpdate = false;

	auto AchievementApi = ApiClient->GetApiPtr<Achievement>();
	if (!AchievementApi.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Initialise - Failed to get Achievement API"));
		return;
	}

	THandler<FAccelByteModelsPaginatedPublicAchievement> OnSuccess =
		THandler<FAccelByteModelsPaginatedPublicAchievement>::CreateRaw(
			this, &FAccelByteAchievementsPanel::OnQueryDefinitionsSuccess);

	FErrorHandler OnError = FErrorHandler::CreateRaw(
		this, &FAccelByteAchievementsPanel::OnAccelByteError);

	// Query all public achievements for this namespace, ordered by list order
	AchievementApi->QueryAchievements(
		Language,
		EAccelByteAchievementListSortBy::NONE,
		OnSuccess,
		OnError,
		0,
		100); // Limit: adjust as needed
}

void FAccelByteAchievementsPanel::Update()
{
	if (!ApiClient.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Update - ApiClient is invalid"));
		return;
	}

	// If definitions aren't loaded yet, remember to fetch user progress once they are
	if (!bDefinitionsLoaded)
	{
		bPendingUserUpdate = true;
		return;
	}

	auto AchievementApi = ApiClient->GetApiPtr<Achievement>();
	if (!AchievementApi.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Update - Failed to get Achievement API"));
		return;
	}

	THandler<FAccelByteModelsPaginatedUserAchievement> OnSuccess =
		THandler<FAccelByteModelsPaginatedUserAchievement>::CreateRaw(
			this, &FAccelByteAchievementsPanel::OnQueryUserAchievementsSuccess);

	FErrorHandler OnError = FErrorHandler::CreateRaw(
		this, &FAccelByteAchievementsPanel::OnAccelByteError);

	// Query current user's achievements (progress + unlocked state)
	AchievementApi->QueryUserAchievements(
		EAccelByteAchievementListSortBy::NONE,
		OnSuccess,
		OnError,
		0,
		100,
		true,
		TEXT(""));
}

void FAccelByteAchievementsPanel::Show(float Width, float Height)
{
	if (bVisible)
	{
		return;
	}

	if (!GEngine || !GEngine->GameViewport)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Show - No GameViewport available"));
		return;
	}

	EnsureWidgetCreated(Width, Height);

	if (!Widget.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::Show - Widget creation failed"));
		return;
	}

	RootWidget = Widget;
	GEngine->GameViewport->AddViewportWidgetContent(Widget.ToSharedRef());

	bVisible = true;

	// Optionally refresh latest player state when shown
	Update();
}

void FAccelByteAchievementsPanel::Hide()
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

TSharedPtr<SWidget> FAccelByteAchievementsPanel::GetWidget() const
{
	return Widget;
}

TSharedRef<SWidget> FAccelByteAchievementsPanel::BuildWidget(float Width, float Height)
{
	EnsureWidgetCreated(Width, Height);
	check(Widget.IsValid());
	return Widget.ToSharedRef();
}

void FAccelByteAchievementsPanel::OnQueryDefinitionsSuccess(const FAccelByteModelsPaginatedPublicAchievement& Result)
{
	Entries.Empty();
	CodeToIndex.Empty();

	for (const FAccelByteModelsPublicAchievement& PublicAchievement : Result.Data)
	{
		TSharedPtr<FAccelByteAchievementEntry> Entry = MakeShared<FAccelByteAchievementEntry>();
		Entry->AchievementCode = PublicAchievement.AchievementCode;
		Entry->Name = FText::FromString(PublicAchievement.Name);
		Entry->Description = FText::FromString(PublicAchievement.Description);

		if (PublicAchievement.LockedIcons.Num() > 0)
		{
			Entry->LockedIconUrl = PublicAchievement.LockedIcons[0].Url;
		}
		if (PublicAchievement.UnlockedIcons.Num() > 0)
		{
			Entry->UnlockedIconUrl = PublicAchievement.UnlockedIcons[0].Url;
		}

		Entry->TargetValue = PublicAchievement.GoalValue;
		Entry->CurrentValue = 0.0f;
		Entry->bUnlocked = false;

		int32 NewIndex = Entries.Add(Entry);
		CodeToIndex.Add(Entry->AchievementCode, NewIndex);
	}

	UE_LOG(LogTemp, Log, TEXT("FAccelByteAchievementsPanel::OnQueryDefinitionsSuccess - Loaded %d definitions"), Entries.Num());

	// Mark definitions as loaded and flush any pending user-progress query
	bDefinitionsLoaded = true;

	// If we have cached user achievements (progress) from an earlier query, apply them now
	if (PendingUserAchievements.Num() > 0)
	{
		ApplyUserAchievements(PendingUserAchievements);
		PendingUserAchievements.Empty();
	}

	if (bPendingUserUpdate)
	{
		bPendingUserUpdate = false;
		Update();
	}

	AsyncTask(ENamedThreads::GameThread, [this]()
	{
		RefreshWidget();
	});
}

void FAccelByteAchievementsPanel::ApplyUserAchievements(const TArray<FAccelByteModelsUserAchievement>& UserAchievements)
{
	// Merge user progress into cached definitions
	for (const FAccelByteModelsUserAchievement& UserAchievement : UserAchievements)
	{
		int32* IndexPtr = CodeToIndex.Find(UserAchievement.AchievementCode);
		if (!IndexPtr)
		{
			continue;
		}

		const int32 Index = *IndexPtr;
		if (!Entries.IsValidIndex(Index))
		{
			continue;
		}

		TSharedPtr<FAccelByteAchievementEntry>& Entry = Entries[Index];
		Entry->CurrentValue = UserAchievement.LatestValue;

		// Status: 1 = In-Progress, 2 = Unlocked
		Entry->bUnlocked = (UserAchievement.Status == 2);

		// If we know the goal value, we can also infer unlocked from progress
		if (!Entry->bUnlocked && Entry->TargetValue > 0.0f)
		{
			if (Entry->CurrentValue >= Entry->TargetValue)
			{
				Entry->bUnlocked = true;
			}
		}

		// Trigger icon download based on lock state if we have URLs
		const FString& IconUrl = Entry->bUnlocked ? Entry->UnlockedIconUrl : Entry->LockedIconUrl;
		if (!IconUrl.IsEmpty())
		{
			DownloadIconForEntry(Index, IconUrl);
		}
	}
}

void FAccelByteAchievementsPanel::OnQueryUserAchievementsSuccess(const FAccelByteModelsPaginatedUserAchievement& Result)
{
	// If definitions are not ready yet, cache the user progress to be applied later
	if (!bDefinitionsLoaded)
	{
		PendingUserAchievements = Result.Data;
		UE_LOG(LogTemp, Log, TEXT("FAccelByteAchievementsPanel::OnQueryUserAchievementsSuccess - Cached %d user achievements (definitions not ready yet)"), Result.Data.Num());
		return;
	}

	ApplyUserAchievements(Result.Data);

	UE_LOG(LogTemp, Log, TEXT("FAccelByteAchievementsPanel::OnQueryUserAchievementsSuccess - Updated %d user achievements"), Result.Data.Num());

	AsyncTask(ENamedThreads::GameThread, [this]()
	{
		RefreshWidget();
	});
}

void FAccelByteAchievementsPanel::OnAccelByteError(int32 ErrorCode, const FString& ErrorMessage)
{
	UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel AccelByte error %d: %s"), ErrorCode, *ErrorMessage);
}

void FAccelByteAchievementsPanel::DownloadIconForEntry(int32 ItemIndex, const FString& IconUrl)
{
	if (IconUrl.IsEmpty())
	{
		return;
	}

	if (!Entries.IsValidIndex(ItemIndex))
	{
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("FAccelByteAchievementsPanel::DownloadIconForEntry - Index %d URL %s"), ItemIndex, *IconUrl);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> HttpRequest = FHttpModule::Get().CreateRequest();
	HttpRequest->SetURL(IconUrl);
	HttpRequest->SetVerb(TEXT("GET"));
	HttpRequest->OnProcessRequestComplete().BindRaw(
		this, &FAccelByteAchievementsPanel::OnIconDownloadComplete, ItemIndex);
	HttpRequest->ProcessRequest();
}

void FAccelByteAchievementsPanel::OnIconDownloadComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful, int32 ItemIndex)
{
	if (!bWasSuccessful || !Response.IsValid() || Response->GetResponseCode() != 200)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::OnIconDownloadComplete - Failed for index %d"), ItemIndex);
		return;
	}

	if (!Entries.IsValidIndex(ItemIndex))
	{
		return;
	}

	const TArray<uint8>& ImageData = Response->GetContent();
	if (ImageData.Num() == 0)
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::OnIconDownloadComplete - Empty image data for index %d"), ItemIndex);
		return;
	}

	IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(FName("ImageWrapper"));
	TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG);

	if (!ImageWrapper->SetCompressed(ImageData.GetData(), ImageData.Num()))
	{
		ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::JPEG);
		if (!ImageWrapper->SetCompressed(ImageData.GetData(), ImageData.Num()))
		{
			UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::OnIconDownloadComplete - Failed to parse image for index %d"), ItemIndex);
			return;
		}
	}

	TArray<uint8> RawData;
	if (!ImageWrapper->GetRaw(ERGBFormat::BGRA, 8, RawData))
	{
		UE_LOG(LogTemp, Warning, TEXT("FAccelByteAchievementsPanel::OnIconDownloadComplete - Failed to get raw data for index %d"), ItemIndex);
		return;
	}

	const int32 Width = ImageWrapper->GetWidth();
	const int32 Height = ImageWrapper->GetHeight();

	AsyncTask(ENamedThreads::GameThread, [this, ItemIndex, Width, Height, RawData]()
	{
		if (!Entries.IsValidIndex(ItemIndex))
		{
			return;
		}

		UTexture2D* Texture = UTexture2D::CreateTransient(Width, Height, PF_B8G8R8A8);
		if (!Texture)
		{
			return;
		}

		Texture->SRGB = true;

		void* MipData = Texture->GetPlatformData()->Mips[0].BulkData.Lock(LOCK_READ_WRITE);
		FMemory::Memcpy(MipData, RawData.GetData(), RawData.Num());
		Texture->GetPlatformData()->Mips[0].BulkData.Unlock();

		Texture->UpdateResource();

		TSharedPtr<FAccelByteAchievementEntry>& Entry = Entries[ItemIndex];
		if (!Entry->IconBrush.IsValid())
		{
			Entry->IconBrush = MakeShared<FSlateBrush>();
		}

		Entry->IconBrush->SetResourceObject(Texture);
		Entry->IconBrush->ImageSize = FVector2D(Width, Height);

		RefreshWidget();
	});
}

void FAccelByteAchievementsPanel::EnsureWidgetCreated(float Width, float Height)
{
	if (Widget.IsValid())
	{
		return;
	}

	SAssignNew(Widget, SAccelByteAchievementsWidget)
		.Width(Width)
		.Height(Height)
		.ItemsSource(&Entries);
}

void FAccelByteAchievementsPanel::RefreshWidget()
{
	if (Widget.IsValid())
	{
		Widget->RequestRefresh();
	}
}

void SAccelByteAchievementRow::Construct(
	const FArguments& InArgs,
	const TSharedRef<STableViewBase>& OwnerTableView)
{
	Item = InArgs._Item;

	STableRow::Construct(
		STableRow::FArguments()
		.Padding(8)
		[
			BuildContent()
		],
		OwnerTableView);
}

TSharedRef<SWidget> SAccelByteAchievementRow::BuildContent()
{
	const FText NameText = Item.IsValid() ? Item->Name : FText::GetEmpty();
	const FText DescText = Item.IsValid() ? Item->Description : FText::GetEmpty();

	return
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot()
		.AutoWidth()
		.VAlign(VAlign_Center)
		.Padding(0, 0, 8, 0)
		[
			SNew(SBox)
			.WidthOverride(48.f)
			.HeightOverride(48.f)
			[
				SAssignNew(IconImage, SImage)
				.Image(this, &SAccelByteAchievementRow::GetIconBrush)
			]
		]
		+ SHorizontalBox::Slot()
		.FillWidth(1.f)
		.VAlign(VAlign_Center)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(STextBlock)
				.Text(NameText)
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 16))
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			[
				SNew(STextBlock)
				.Text(DescText)
				.Font(FCoreStyle::GetDefaultFontStyle("Regular", 12))
				.WrapTextAt(400.f)
			]
			+ SVerticalBox::Slot()
			.AutoHeight()
			.Padding(0, 4, 0, 0)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot()
				.FillWidth(1.f)
				[
					SNew(SProgressBar)
					.Percent(this, &SAccelByteAchievementRow::GetProgressPercent)
				]
				+ SHorizontalBox::Slot()
				.AutoWidth()
				.Padding(4.f, 0.f)
				.VAlign(VAlign_Center)
				[
					SNew(STextBlock)
					.Text(this, &SAccelByteAchievementRow::GetProgressText)
					.Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
				]
			]
		];
}

const FSlateBrush* SAccelByteAchievementRow::GetIconBrush() const
{
	if (Item.IsValid() && Item->IconBrush.IsValid())
	{
		return Item->IconBrush.Get();
	}

	return FCoreStyle::Get().GetBrush("Default");
}

TOptional<float> SAccelByteAchievementRow::GetProgressPercent() const
{
	if (Item.IsValid() && Item->TargetValue > 0.0f)
	{
		const float ClampedCurrent = FMath::Clamp(Item->CurrentValue, 0.0f, Item->TargetValue);
		return ClampedCurrent / Item->TargetValue;
	}

	if (Item.IsValid() && Item->bUnlocked)
	{
		return 1.0f;
	}

	return TOptional<float>();
}

FText SAccelByteAchievementRow::GetProgressText() const
{
	if (Item.IsValid() && Item->TargetValue > 0.0f)
	{
		const float ClampedCurrent = FMath::Clamp(Item->CurrentValue, 0.0f, Item->TargetValue);
		return FText::Format(
			NSLOCTEXT("AccelByteAchievements", "ProgressFormat", "{0} / {1}"),
			FText::AsNumber(FMath::FloorToFloat(ClampedCurrent)),
			FText::AsNumber(FMath::FloorToFloat(Item->TargetValue)));
	}

	if (Item.IsValid())
	{
		return Item->bUnlocked
			? NSLOCTEXT("AccelByteAchievements", "Unlocked", "Unlocked")
			: NSLOCTEXT("AccelByteAchievements", "Locked", "Locked");
	}

	return FText::GetEmpty();
}

void SAccelByteAchievementsWidget::Construct(const FArguments& InArgs)
{
	Items = InArgs._ItemsSource;

	ChildSlot
	[
		SNew(SBox)
		.WidthOverride(InArgs._Width)
		.HeightOverride(InArgs._Height)
		[
			SNew(SBorder)
			.Padding(12)
			.BorderImage(FCoreStyle::Get().GetBrush("BlackBrush"))
			[
				SNew(SVerticalBox)

				+ SVerticalBox::Slot()
				.AutoHeight()
				.Padding(0, 0, 0, 8)
				[
					SNew(STextBlock)
					.Text(NSLOCTEXT("AccelByteAchievements", "Title", "Achievements"))
					.Font(FCoreStyle::GetDefaultFontStyle("Bold", 22))
				]

				+ SVerticalBox::Slot()
				.FillHeight(1.f)
				[
					SAssignNew(ListView, SListView<TSharedPtr<FAccelByteAchievementEntry>>)
					.ListItemsSource(Items)
					.SelectionMode(ESelectionMode::None)
					.OnGenerateRow(this, &SAccelByteAchievementsWidget::OnGenerateRow)
				]
			]
		]
	];
}

void SAccelByteAchievementsWidget::RequestRefresh()
{
	if (ListView.IsValid())
	{
		ListView->RequestListRefresh();
	}
}

TSharedRef<ITableRow> SAccelByteAchievementsWidget::OnGenerateRow(
	TSharedPtr<FAccelByteAchievementEntry> Item,
	const TSharedRef<STableViewBase>& OwnerTable)
{
	return SNew(SAccelByteAchievementRow, OwnerTable)
		.Item(Item);
}

