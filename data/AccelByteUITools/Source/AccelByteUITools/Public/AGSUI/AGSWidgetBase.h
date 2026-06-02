#pragma once

#include "Blueprint/IUserObjectListEntry.h"
#include "Blueprint/UserWidget.h"
#include "CommonActivatableWidget.h"
#include "AGSWidgetBase.generated.h"

class UButton;
class UEditableTextBox;
class UImage;
class UTextBlock;
class UTexture2D;
class UWidget;
class UWidgetSwitcher;

UENUM(BlueprintType)
enum class EAGSUIState : uint8
{
	Idle,
	Loading,
	Success,
	Empty,
	Error
};

UENUM(BlueprintType)
enum class EAGSStatusType : uint8
{
	Info,
	Success,
	Warning,
	Error
};

UENUM(BlueprintType)
enum class EAGSButtonVariant : uint8
{
	Primary,
	Secondary,
	Danger,
	Icon
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FAGSUIActionEvent);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FAGSUISubmitEvent, const FString&, Value);

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSWidgetBase : public UUserWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetDisabled(bool bInDisabled);

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI")
	bool bIsDisabled = false;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSStateWidgetBase : public UAGSWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLoading(bool bInLoading);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetState(EAGSUIState InState);

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI")
	EAGSUIState CurrentState = EAGSUIState::Success;

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI")
	bool bIsLoading = false;

protected:
	virtual void NativeOnInitialized() override;

	void UpdateStateVisibility();

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidget> IdlePanel;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidget> LoadingPanel;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidget> SuccessPanel;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidget> EmptyPanel;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidget> ErrorPanel;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|State")
	TObjectPtr<UWidgetSwitcher> StateSwitcher;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSLabelValueWidgetBase : public UAGSWidgetBase, public IUserObjectListEntry
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InLabel);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetValue(const FText& InValue);

	UFUNCTION(BlueprintCallable, Category = "AGS UI|List Entry")
	UObject* GetListItemObject() const { return ListItemObject.Get(); }

protected:
	virtual void NativeOnListItemObjectSet(UObject* InListItemObject) override;

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI|List Entry")
	TObjectPtr<UObject> ListItemObject;

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> LabelText;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> ValueText;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSButtonBase : public UUserWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InLabel);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	EAGSButtonVariant Variant = EAGSButtonVariant::Primary;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	FText DefaultLabel = NSLOCTEXT("AGSUI", "ButtonDefaultLabel", "Button");

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	void SetSelected(bool bSelected);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	FLinearColor SelectedColor = FLinearColor(0.043f, 0.424f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	FLinearColor SelectedTextColor = FLinearColor(1.0f, 1.0f, 1.0f, 1.0f);

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI")
	bool bIsSelected = false;

	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUIActionEvent OnClicked;

protected:
	virtual void NativeOnInitialized() override;
	virtual void NativePreConstruct() override;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UButton> InteractiveButton;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> ButtonText;

	UFUNCTION()
	void HandleClicked();

private:
	FButtonStyle CachedButtonStyle;
	FSlateColor CachedTextColor;
	bool bTextColorCached = false;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSTextInputBase : public UAGSWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InLabel);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetValue(const FText& InValue);

	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUISubmitEvent OnSubmit;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	FText DefaultHintText;

protected:
	virtual void NativeOnInitialized() override;
	virtual void NativePreConstruct() override;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> LabelText;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UEditableTextBox> ValueInput;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UAGSButtonBase> SubmitButton;

	UFUNCTION()
	void HandleSubmitClicked();
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSStatusMessageBase : public UAGSLabelValueWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetStatus(EAGSStatusType InStatusType, const FText& InMessage);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetError(const FText& InMessage);

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI")
	EAGSStatusType StatusType = EAGSStatusType::Info;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSActionPanelBase : public UAGSStateWidgetBase
{
	GENERATED_BODY()

public:
	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUIActionEvent OnConfirm;

	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUIActionEvent OnCancel;

	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUIActionEvent OnRetry;

protected:
	virtual void NativeOnInitialized() override;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UAGSButtonBase> ConfirmButton;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UAGSButtonBase> CancelButton;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UAGSButtonBase> RetryButton;

	UFUNCTION()
	void HandleConfirmClicked();

	UFUNCTION()
	void HandleCancelClicked();

	UFUNCTION()
	void HandleRetryClicked();
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSListRowBase : public UAGSLabelValueWidgetBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSFeatureBlockBase : public UAGSStateWidgetBase, public IUserObjectListEntry
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI|List Entry")
	UObject* GetListItemObject() const { return ListItemObject.Get(); }

protected:
	virtual void NativeOnListItemObjectSet(UObject* InListItemObject) override;

	UPROPERTY(BlueprintReadOnly, Category = "AGS UI|List Entry")
	TObjectPtr<UObject> ListItemObject;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSPanelBase : public UAGSStateWidgetBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSLoginBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSMatchmakingStatusBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSFriendsListBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSPartyBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSLeaderboardBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSStoreGridBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSCloudSaveSlotsBlockBase : public UAGSFeatureBlockBase
{
	GENERATED_BODY()
};

// Panel base for Common UI mode. Overrides GetDesiredFocusTarget so generated
// blueprints don't trigger the "wasn't implemented" gamepad warning at activation.
UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSCommonActivatableBase : public UCommonActivatableWidget
{
	GENERATED_BODY()

protected:
	virtual UWidget* NativeGetDesiredFocusTarget() const override;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSAvatarBase : public UAGSLabelValueWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetAvatarImage(UTexture2D* InTexture);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UImage> AvatarImage;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSIconButtonBase : public UAGSButtonBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetIcon(UTexture2D* InTexture);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UImage> ButtonIcon;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSLoadingIndicatorBase : public UAGSStateWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetStatusText(const FText& InText);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> StatusText;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSEmptyStateBase : public UAGSStateWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InText);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetStatusText(const FText& InText);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> LabelText;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> StatusText;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSErrorStateBase : public UAGSActionPanelBase
{
	GENERATED_BODY()
	// Inherits: RetryButton (UAGSButtonBase*), OnRetry (FAGSUIActionEvent), SetState(), SetLoading()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InText);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetStatusText(const FText& InText);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> LabelText;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> StatusText;
};

UCLASS(Blueprintable)
class ACCELBYTEUITOOLS_API UAGSBasePanelBase : public UAGSStateWidgetBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InText);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UTextBlock> LabelText;
};
