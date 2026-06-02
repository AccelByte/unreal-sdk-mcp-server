#pragma once

#include "CoreMinimal.h"
#include "CommonButtonBase.h"
#include "CommonTextBlock.h"
#include "AGSWidgetBase.h"
#include "AGSCommonWidgetBase.generated.h"

class UImage;

// Common UI-backed button base. Mirrors UAGSButtonBase API so Script-backed C++
// is identical between UMG and Common UI modes — bind as UAGSCommonButtonBase*,
// call SetLabel/SetSelected/OnClicked the same way.
UCLASS(Abstract, Blueprintable)
class ACCELBYTEUITOOLS_API UAGSCommonButtonBase : public UCommonButtonBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetLabel(const FText& InLabel);

	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	void SetSelected(bool bInSelected);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AGS UI")
	EAGSButtonVariant Variant = EAGSButtonVariant::Primary;

	// Unified click delegate matching FAGSUIActionEvent — keeps Script-backed
	// C++ identical regardless of whether the panel targets UMG or Common UI.
	UPROPERTY(BlueprintAssignable, Category = "AGS UI|Events")
	FAGSUIActionEvent OnClicked;

protected:
	// Applies the default style class matching Variant when no style has been set explicitly.
	virtual void NativePreConstruct() override;

	// UCommonButtonBase hook — rebroadcasts to OnClicked for API consistency.
	virtual void NativeOnClicked() override;

	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UCommonTextBlock> ButtonText;
};

// Icon variant — extends UAGSCommonButtonBase with an optional icon image.
UCLASS(Abstract, Blueprintable)
class ACCELBYTEUITOOLS_API UAGSCommonIconButtonBase : public UAGSCommonButtonBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AGS UI")
	virtual void SetIcon(UTexture2D* InTexture);

protected:
	UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional), Category = "AGS UI|Bindings")
	TObjectPtr<UImage> ButtonIcon;
};
